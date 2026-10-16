#!/usr/bin/env python3
"""Local receipts and dependency checks; never runs an LLM or scientific analysis."""
import argparse
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import uuid

STAGES = ("question", "outline", "draft", "audit", "journal")
ROUTES = {
    "question": ["academic-research-suite"],
    "outline": ["paper-skill"],
    "draft": ["paper-skill"],
    "audit": ["ref-verify", "anti-defensive-writing"],
    "journal": ["journal-recommender"],
}
PROMPTS = dict(zip(STAGES, (
    "01-question.md", "02-outline.md", "03-draft.md", "04-audit.md", "05-journal.md"
)))
SKILL_ROOT = Path(__file__).resolve().parents[1]


def now():
    return datetime.now(timezone.utc).isoformat()


def meta(root):
    return root / ".paper-workflow"


def inside(path, root):
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def resolve(root, value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("File paths must be nonempty strings")
    path = Path(value).expanduser()
    return (path if path.is_absolute() else root / path).resolve()


def digest(path):
    hasher = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def snapshots(root, values, internal=False):
    if not isinstance(values, list):
        raise ValueError("File collections must be lists")
    result = {}
    for value in values:
        path = resolve(root, value)
        if internal and not inside(path, root):
            raise ValueError("Output/prompt must stay inside project: " + str(path))
        if path == meta(root) / "state.json":
            raise ValueError("State file cannot be its own input or output")
        if not path.is_file() or not path.stat().st_size:
            raise ValueError("Missing or empty file: " + str(path))
        result[str(path)] = digest(path)
    return result


def atomic_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".write-", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


@contextmanager
def locked(root):
    directory = meta(root)
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / ".lock"
    try:
        fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError("Another writer or stale lock exists; inspect before retrying: " + str(lock))
    try:
        with os.fdopen(fd, "w") as stream:
            stream.write(str(os.getpid()))
        yield
    finally:
        lock.unlink()


def read_state(root):
    path = meta(root) / "state.json"
    if not path.exists():
        return None
    state = json.loads(path.read_text(encoding="utf-8"))
    if state.get("schema_version") != 1 or state.get("project") != str(root):
        raise ValueError("Unsupported state version or project moved; review state before using it")
    if not isinstance(state.get("stages"), dict):
        raise ValueError("Invalid stage registry")
    return state


def initialize(root):
    with locked(root):
        state = read_state(root)
        if state is None:
            state = {"schema_version": 1, "project": str(root), "created_at": now(), "stages": {}}
            atomic_json(meta(root) / "state.json", state)
        for folder in ("drafts", ".paper-workflow/prompts", ".paper-workflow/history"):
            (root / folder).mkdir(parents=True, exist_ok=True)
    return {"initialized": True, "project": str(root), "preserved_existing": True}


def stage_statuses(state):
    records = (state or {}).get("stages", {})
    result = {}
    for stage in STAGES:
        record = records.get(stage)
        if not record:
            result[stage] = {"status": "pending", "reasons": []}
            continue
        reasons = []
        for group in ("inputs", "outputs", "resources", "prompt"):
            for name, old_hash in record["snapshots"][group].items():
                path = Path(name)
                if not path.is_file():
                    reasons.append("missing " + group + ": " + name)
                elif digest(path) != old_hash:
                    reasons.append("changed " + group + ": " + name)
        for dependency, run_id in record["dependency_runs"].items():
            previous = records.get(dependency)
            if not previous or previous["run_id"] != run_id:
                reasons.append("dependency rerun: " + dependency)
            elif result[dependency]["status"] != "complete":
                reasons.append("dependency not current/complete: " + dependency)
        result[stage] = {
            "status": "stale" if reasons else record["status"],
            "recorded_status": record["status"],
            "reasons": reasons,
            "blockers": record["blockers"],
            "notes": record.get("notes", ""),
            "outputs": list(record["snapshots"]["outputs"]),
        }
    return result


def find_skill(skills_root, name):
    """Resolve a named skill in flat or categorized roots without scanning support trees."""
    direct = skills_root / name / "SKILL.md"
    if direct.is_file():
        return [direct]
    matches, seen = [], set()
    for folder, dirs, files in os.walk(str(skills_root), followlinks=True):
        path = Path(folder)
        real = path.resolve()
        if real in seen:
            dirs[:] = []
            continue
        seen.add(real)
        dirs[:] = [d for d in dirs if not d.startswith(".") and ".backup" not in d and d != "__pycache__"]
        if "SKILL.md" in files:
            if path.name == name:
                matches.append(path / "SKILL.md")
            dirs[:] = []
    return sorted(matches)


def default_skills_root(runtime="auto"):
    if runtime == "auto":
        runtime = "zcode" if os.environ.get("ZCODE_DATA_BASE_DIR") else ("hermes" if os.environ.get("HERMES_HOME") else "codex")
    if runtime == "zcode":
        base = os.environ.get("ZCODE_DATA_BASE_DIR") or str(Path.home() / ".zcode")
    else:
        key, fallback = ("HERMES_HOME", ".hermes") if runtime == "hermes" else ("CODEX_HOME", ".codex")
        base = os.environ.get(key) or str(Path.home() / fallback)
    return Path(base).expanduser() / "skills"


def inspect(root, skills_root):
    state = read_state(root)
    statuses = stage_statuses(state)
    next_stage = next((s for s in STAGES if statuses[s]["status"] != "complete"), None)
    installed = {}
    for name in sorted({n for route in ROUTES.values() for n in route}):
        matches = find_skill(skills_root, name)
        installed[name] = {
            "path": str(matches[0]) if len(matches) == 1 else None,
            "present": len(matches) == 1,
            "ambiguous": len(matches) > 1,
            "candidates": [str(p) for p in matches],
        }
    return {
        "project": str(root), "initialized": state is not None,
        "stages": statuses, "suggested_stage_from_records": next_stage,
        "suggestion_scope": "Advisory only; inspect user scope and existing materials before routing",
        "skills": installed,
        "next_route": None if next_stage is None else {
            "skills": ROUTES[next_stage],
            "prompt_template": str(SKILL_ROOT / "references" / PROMPTS[next_stage]),
        },
    }


def string_list(receipt, key):
    value = receipt.get(key)
    if not isinstance(value, list) or any(not isinstance(x, str) or not x.strip() for x in value):
        raise ValueError(key + " must be a list of nonempty strings")
    return value


def record(root, receipt):
    if not isinstance(receipt, dict):
        raise ValueError("Receipt must be a JSON object")
    stage, status = receipt.get("stage"), receipt.get("status")
    if stage not in STAGES or status not in ("partial", "blocked", "complete"):
        raise ValueError("Invalid stage or status")
    checks = string_list(receipt, "checks")
    blockers = string_list(receipt, "blockers")
    dependencies = string_list(receipt, "depends_on")
    if len(dependencies) != len(set(dependencies)):
        raise ValueError("Duplicate dependencies")
    for dependency in dependencies:
        if dependency not in STAGES or STAGES.index(dependency) >= STAGES.index(stage):
            raise ValueError("Dependencies must precede the current stage")
    if status == "complete" and (blockers or not checks):
        raise ValueError("Complete requires actual checks and no blockers")
    if status == "blocked" and not blockers:
        raise ValueError("Blocked requires a reason")
    with locked(root):
        state = read_state(root)
        if state is None:
            raise ValueError("Initialize project before recording a stage")
        effective = stage_statuses(state)
        dependency_runs = {}
        for dependency in dependencies:
            prior = state["stages"].get(dependency)
            if not prior:
                raise ValueError("Unrecorded dependency: " + dependency)
            if status == "complete" and effective[dependency]["status"] != "complete":
                raise ValueError("Dependency not current/complete: " + dependency)
            dependency_runs[dependency] = prior["run_id"]
        snaps = {
            "inputs": snapshots(root, string_list(receipt, "inputs")),
            "outputs": snapshots(root, string_list(receipt, "outputs"), internal=True),
            "resources": snapshots(root, string_list(receipt, "resources")),
            "prompt": snapshots(root, [receipt.get("prompt")], internal=True),
        }
        if status == "complete" and any(not snaps[k] for k in ("inputs", "outputs", "resources")):
            raise ValueError("Complete requires real inputs, outputs, and used skill resources")
        run_id = stage + "-" + uuid.uuid4().hex
        saved = dict(receipt, run_id=run_id, recorded_at=now(), snapshots=snaps,
                     dependency_runs=dependency_runs)
        # Hash once again before committing to detect changes while making the receipt.
        for group in snaps.values():
            for name, expected in group.items():
                if digest(Path(name)) != expected:
                    raise ValueError("File changed during recording: " + name)
        archive = meta(root) / "history" / (run_id + ".json")
        atomic_json(archive, saved)
        state["stages"][stage] = saved
        state["updated_at"] = now()
        atomic_json(meta(root) / "state.json", state)
    return {"recorded": stage, "status": status, "receipt": str(archive)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("init", "inspect", "record"))
    parser.add_argument("--project", required=True)
    parser.add_argument("--receipt")
    parser.add_argument("--runtime", choices=("auto", "codex", "hermes", "zcode"), default="auto")
    parser.add_argument("--skills-root", help="Explicit skills directory; overrides --runtime")
    args = parser.parse_args()
    root = Path(args.project).expanduser().resolve()
    try:
        if args.command == "init":
            result = initialize(root)
        elif args.command == "inspect":
            skill_root = Path(args.skills_root).expanduser() if args.skills_root else default_skills_root(args.runtime)
            result = inspect(root, skill_root.resolve())
        else:
            if not args.receipt:
                parser.error("record requires --receipt")
            result = record(root, json.loads(Path(args.receipt).read_text(encoding="utf-8")))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
