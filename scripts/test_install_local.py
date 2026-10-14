from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import install_local as installer


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="paper-install-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.source = self.root / "source"
        self.source.mkdir()
        (self.source / "SKILL.md").write_text("Synthetic skill")
        (self.source / ".git").mkdir()
        (self.source / ".git/private").write_text("Never copy Git internals")
        self.target = self.root / "target"

    def test_copy_omits_git_and_refuses_overwrite(self):
        with patch.object(installer, "SKILL_ROOT", self.source):
            installer.install(self.target)
            dest = self.target / "sci-paper-workflow"
            self.assertTrue((dest / "SKILL.md").is_file())
            self.assertFalse((dest / ".git").exists())
            (dest / "SKILL.md").write_text("User changed")
            with self.assertRaises(ValueError):
                installer.install(self.target)
            self.assertEqual("User changed", (dest / "SKILL.md").read_text())

    def test_link_reuse_and_dependency_preflight(self):
        with patch.object(installer, "SKILL_ROOT", self.source):
            installer.install(self.target, mode="link")
            self.assertEqual([], installer.install(self.target, mode="link")["installed"])
            absent = self.root / "other-target"
            with self.assertRaises(ValueError):
                installer.install(absent, self.root / "missing-dependencies", mode="link")
            self.assertFalse(absent.exists())

    def test_all_dependencies_link(self):
        dependencies = self.root / "dependencies"
        for name in {n for values in installer.ROUTES.values() for n in values}:
            skill = dependencies / "research" / name
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text("Synthetic dependency")
        with patch.object(installer, "SKILL_ROOT", self.source):
            report = installer.install(self.target, dependencies, mode="link")
            self.assertEqual(6, len(report["installed"]))
            self.assertTrue(all(Path(p).is_symlink() for p in report["installed"]))


if __name__ == "__main__":
    unittest.main()
