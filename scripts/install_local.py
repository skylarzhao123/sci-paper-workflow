#!/usr/bin/env python3
"""Install this skill plus already-installed dependencies without overwriting existing skills."""
import argparse
import json
from pathlib import Path
import shutil
import sys

from workflow import ROUTES, SKILL_ROOT, default_skills_root, find_skill


def install(target, source_root=None, mode="copy"):
    sources = {"sci-paper-workflow": SKILL_ROOT}
    if source_root:
        for name in sorted({n for route in ROUTES.values() for n in route}):
            matches = find_skill(source_root, name)
            if len(matches) != 1:
                raise ValueError("Dependency missing or ambiguous: " + name)
            sources[name] = matches[0].parent
    # Validate every destination first; never replace another installation.
    plans = []
    for name, source in sources.items():
        dest = target / name
        if dest.exists() or dest.is_symlink():
            if dest.resolve() == source.resolve():
                continue
            raise ValueError("Destination exists; review before updating: " + str(dest))
        if dest.resolve().is_relative_to(source.resolve()):
            raise ValueError("Cannot install a skill inside its source")
        plans.append((source, dest))
    target.mkdir(parents=True, exist_ok=True)
    created = []
    try:
        for source, dest in plans:
            if mode == "link":
                dest.symlink_to(source.resolve(), target_is_directory=True)
                created.append(dest)
            else:
                # Mark only the just-created directory for rollback.
                dest.mkdir()
                created.append(dest)
                shutil.copytree(source, dest, dirs_exist_ok=True,
                    ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc", ".DS_Store"))
    except Exception:
        for dest in reversed(created):
            if dest.is_symlink():
                dest.unlink()
            else:
                shutil.rmtree(dest)
        raise
    return {"mode": mode, "installed": [str(p) for p in created],
            "dependencies_included": source_root is not None}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", choices=("hermes", "codex"), required=True)
    parser.add_argument("--skills-dir", help="Explicit target skills root; e.g. a Hermes profile/research directory")
    parser.add_argument("--dependency-root", help="Existing local skill library containing all five dependencies")
    parser.add_argument("--mode", choices=("copy", "link"), default="copy")
    args = parser.parse_args()
    try:
        target = Path(args.skills_dir).expanduser().resolve() if args.skills_dir else default_skills_root(args.target)
        source = Path(args.dependency_root).expanduser().resolve() if args.dependency_root else None
        print(json.dumps(install(target, source, args.mode), ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError) as error:
        print(str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
