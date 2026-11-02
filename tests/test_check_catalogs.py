"""Tests for scripts/check-catalogs.py: the catalogs pass, each planted break fails."""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class CheckCatalogsTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.root = Path(self.dir.name)
        for name in [".claude-plugin", ".agents"]:
            shutil.copytree(ROOT / name, self.root / name)
        shutil.copy(ROOT / "README.md", self.root / "README.md")
        self.claude = self.root / ".claude-plugin/marketplace.json"
        self.codex = self.root / ".agents/plugins/marketplace.json"

    def tearDown(self):
        self.dir.cleanup()

    def check(self):
        return subprocess.run([sys.executable, "-I", str(ROOT / "scripts/check-catalogs.py"), str(self.root)],
                              capture_output=True, text=True)

    def edit(self, path, change):
        data = json.loads(path.read_text())
        change(data)
        path.write_text(json.dumps(data))

    def test_catalogs_pass(self):
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_fork_outside_owners_fails(self):
        self.edit(self.claude, lambda d: d["plugins"][0]["source"].update(repo="evil/finolabs-vibecode"))
        self.edit(self.codex, lambda d: d["plugins"][0]["source"].update(url="https://github.com/evil/finolabs-vibecode.git"))
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("source owner evil is not in OWNERS", result.stdout)

    def test_catalogs_out_of_step_fail(self):
        self.edit(self.codex, lambda d: d["plugins"].pop())
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("plugin lists differ", result.stdout)

    def test_sources_that_differ_fail(self):
        self.edit(self.codex, lambda d: d["plugins"][1]["source"].update(url="https://github.com/fioenix/other.git"))
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("sources differ", result.stdout)

    def test_string_source_reports_instead_of_crashing(self):
        self.edit(self.codex, lambda d: d["plugins"][0].update(source="https://github.com/fioenix/agybird.git"))
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("sources differ", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_readme_table_out_of_step_fails(self):
        readme = self.root / "README.md"
        readme.write_text(readme.read_text().replace("| [markmap-skills](https://github.com/fioenix/markmap-skills)", "| [markmap](https://github.com/fioenix/markmap-skills)"))
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("README table lists", result.stdout)


if __name__ == "__main__":
    unittest.main()
