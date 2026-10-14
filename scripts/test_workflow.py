"""Offline checks for preservation, resume state, and dependency invalidation."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import workflow as w


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="sci-workflow-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        w.initialize(self.root)
        self.put("raw.txt", "Synthetic test fixture, not scientific evidence.")
        self.put("resource.md", "Test-only skill resource")
        self.put("prompt.md", "Test-only resolved task")

    def put(self, path, text):
        target = self.root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def receipt(self, stage, dependencies=None, status="complete"):
        output = stage + "-output.md"
        self.put(output, "Synthetic output " + stage)
        return {
            "stage": stage, "status": status, "depends_on": dependencies or [],
            "inputs": ["raw.txt"], "outputs": [output], "resources": ["resource.md"],
            "prompt": "prompt.md", "checks": ["Synthetic file fixture check only"],
            "blockers": [], "notes": "Offline state test; no scientific verification",
        }

    def statuses(self):
        return w.stage_statuses(w.read_state(self.root))

    def test_init_preserves_existing_content_and_state(self):
        self.put("question.md", "User-owned existing question")
        w.record(self.root, self.receipt("question"))
        before = (w.meta(self.root) / "state.json").read_bytes()
        w.initialize(self.root)
        self.assertEqual(before, (w.meta(self.root) / "state.json").read_bytes())
        self.assertEqual("User-owned existing question", (self.root / "question.md").read_text())

    def test_full_chain_and_changed_source_propagation(self):
        for i, stage in enumerate(w.STAGES):
            receipt = self.receipt(stage, [w.STAGES[i - 1]] if i else [])
            if i:
                receipt["inputs"] = [w.STAGES[i - 1] + "-output.md"]
            w.record(self.root, receipt)
        self.assertTrue(all(x["status"] == "complete" for x in self.statuses().values()))
        self.put("raw.txt", "Changed fixture")
        self.assertTrue(all(x["status"] == "stale" for x in self.statuses().values()))

    def test_changed_output_resource_and_prompt_invalidate(self):
        for path in ("question-output.md", "resource.md", "prompt.md"):
            with self.subTest(path=path):
                w.record(self.root, self.receipt("question"))
                self.put(path, "Changed " + path)
                self.assertEqual("stale", self.statuses()["question"]["status"])

    def test_missing_output_invalidates(self):
        w.record(self.root, self.receipt("question"))
        (self.root / "question-output.md").unlink()
        self.assertEqual("stale", self.statuses()["question"]["status"])

    def test_rerun_invalidates_dependents_even_if_bytes_match(self):
        first = self.receipt("question")
        w.record(self.root, first)
        w.record(self.root, self.receipt("outline", ["question"]))
        w.record(self.root, first)
        self.assertEqual("stale", self.statuses()["outline"]["status"])
        self.assertEqual(3, len(list((w.meta(self.root) / "history").glob("*.json"))))

    def test_direct_audit_needs_no_fabricated_predecessors(self):
        w.record(self.root, self.receipt("audit"))
        states = self.statuses()
        self.assertEqual("complete", states["audit"]["status"])
        self.assertEqual("pending", states["question"]["status"])

    def test_complete_rejects_blockers_empty_output_missing_checks(self):
        receipt = self.receipt("question")
        for changes in ({"blockers": ["Missing source"]}, {"outputs": []}, {"checks": []}):
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                w.record(self.root, dict(receipt, **changes))
        self.put("empty.md", "")
        with self.assertRaises(ValueError):
            w.record(self.root, dict(receipt, outputs=["empty.md"]))
        self.assertEqual({}, w.read_state(self.root)["stages"])

    def test_blocked_and_partial_survive_resume(self):
        receipt = self.receipt("draft", status="blocked")
        receipt.update(blockers=["No real results"], outputs=[], resources=[])
        w.record(self.root, receipt)
        w.initialize(self.root)
        self.assertEqual("blocked", self.statuses()["draft"]["status"])
        w.record(self.root, self.receipt("draft", status="partial"))
        self.assertEqual("partial", self.statuses()["draft"]["status"])

    def test_stale_dependency_cannot_complete_and_cycles_rejected(self):
        w.record(self.root, self.receipt("question"))
        self.put("raw.txt", "Changed")
        for receipt in (self.receipt("outline", ["question"]), self.receipt("question", ["audit"])):
            with self.assertRaises(ValueError):
                w.record(self.root, receipt)

    def test_output_path_boundary_and_lock(self):
        with tempfile.TemporaryDirectory() as outside:
            other = Path(outside) / "outside.md"
            other.write_text("Outside")
            with self.assertRaises(ValueError):
                w.record(self.root, dict(self.receipt("question"), outputs=[str(other)]))
        with w.locked(self.root), self.assertRaises(ValueError):
            w.initialize(self.root)

    def test_inspect_only_and_routes_resolve(self):
        before = (w.meta(self.root) / "state.json").read_bytes()
        report = w.inspect(self.root, self.root / "absent-skills")
        self.assertEqual("question", report["suggested_stage_from_records"])
        self.assertTrue(all(not v["present"] for v in report["skills"].values()))
        self.assertEqual(before, (w.meta(self.root) / "state.json").read_bytes())
        for name in w.PROMPTS.values():
            self.assertTrue((w.SKILL_ROOT / "references" / name).is_file())

    def test_hermes_categories_and_ambiguity(self):
        skills = self.root / "skills"
        self.put("skills/research/paper-skill/SKILL.md", "Test skill")
        report = w.inspect(self.root, skills)
        self.assertTrue(report["skills"]["paper-skill"]["present"])
        self.put("skills/other/paper-skill/SKILL.md", "Different test skill")
        report = w.inspect(self.root, skills)
        self.assertFalse(report["skills"]["paper-skill"]["present"])
        self.assertTrue(report["skills"]["paper-skill"]["ambiguous"])

    def test_profile_root_and_explicit_runtime(self):
        with patch.dict(w.os.environ, {"HERMES_HOME": str(self.root / "profile"),
                                      "CODEX_HOME": str(self.root / "codex")}):
            self.assertEqual(self.root / "profile/skills", w.default_skills_root())
            self.assertEqual(self.root / "codex/skills", w.default_skills_root("codex"))

    def test_symlink_loop_and_backup_not_traversed(self):
        skills = self.root / "skills"
        skills.mkdir()
        (skills / "loop").symlink_to(skills, target_is_directory=True)
        self.put("skills/old.backup/paper-skill/SKILL.md", "Old test skill")
        self.assertEqual([], w.find_skill(skills, "paper-skill"))


if __name__ == "__main__":
    unittest.main()
