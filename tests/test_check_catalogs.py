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

    def test_path_traversal_outside_owners_fails(self):
        self.edit(self.claude, lambda d: d["plugins"][0]["source"].update(repo="finolabs/../evil/x"))
        self.edit(self.codex, lambda d: d["plugins"][0]["source"].update(url="https://github.com/finolabs/../evil/x.git"))
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("is not a plain owner/repository", result.stdout)

    def test_catalogs_out_of_step_fail(self):
        self.edit(self.codex, lambda d: d["plugins"].pop())
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("plugin lists differ", result.stdout)

    def test_sources_that_differ_fail(self):
        self.edit(self.codex, lambda d: d["plugins"][1]["source"].update(url="https://github.com/finolabs/other.git"))
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("sources differ", result.stdout)

    def test_string_source_reports_instead_of_crashing(self):
        self.edit(self.codex, lambda d: d["plugins"][0].update(source="https://github.com/finolabs/agybird.git"))
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("sources differ", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_readme_table_out_of_step_fails(self):
        readme = self.root / "README.md"
        readme.write_text(readme.read_text().replace("| [markmap-skills](https://github.com/finolabs/markmap-skills)", "| [markmap](https://github.com/finolabs/markmap-skills)"))
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("README table lists", result.stdout)

    def test_description_outside_length_range_fails(self):
        self.edit(self.claude, lambda d: d["plugins"][0].update(description="Too short."))
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("description is 10 characters, expected 120-160", result.stdout)

    def test_readme_description_out_of_step_fails(self):
        self.edit(self.claude, lambda d: d["plugins"][1].update(description=d["plugins"][1]["description"] + " "))
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("README table description differs from the catalog entry", result.stdout)


class RemoteManifestsTest(unittest.TestCase):
    """--remote compares each plugin's three manifests with its catalog entry, read from a local tree."""

    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.base = Path(self.dir.name)
        catalog = json.loads((ROOT / ".claude-plugin/marketplace.json").read_text())
        for entry in catalog["plugins"]:
            home = self.base / entry["source"]["repo"] / "HEAD"
            for manifest in (".claude-plugin", ".codex-plugin", ".antigravity-plugin"):
                (home / manifest).mkdir(parents=True)
                (home / manifest / "plugin.json").write_text(json.dumps(
                    {"name": entry["name"], "description": entry["description"], "keywords": entry["keywords"]}))
        self.catalog = catalog

    def tearDown(self):
        self.dir.cleanup()

    def check(self):
        env = {"CATALOG_RAW_BASE": self.base.as_uri(), "PATH": "/usr/bin:/bin"}
        return subprocess.run([sys.executable, "-I", str(ROOT / "scripts/check-catalogs.py"), "--remote"],
                              capture_output=True, text=True, env=env)

    def test_matching_manifests_pass(self):
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_manifest_description_drift_fails(self):
        path = self.base / "finolabs/agybird/HEAD/.antigravity-plugin/plugin.json"
        data = json.loads(path.read_text())
        data["description"] = "A different description."
        path.write_text(json.dumps(data))
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("agybird: .antigravity-plugin/plugin.json description differs from the catalog entry", result.stdout)

    def test_manifest_keyword_drift_fails(self):
        path = self.base / "finolabs/vietnamizer/HEAD/.codex-plugin/plugin.json"
        data = json.loads(path.read_text())
        data["keywords"] = data["keywords"][:-1]
        path.write_text(json.dumps(data))
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("vietnamizer: .codex-plugin/plugin.json keywords differs from the catalog entry", result.stdout)

    def test_missing_antigravity_manifest_fails(self):
        (self.base / "finolabs/markmap-skills/HEAD/.antigravity-plugin/plugin.json").unlink()
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("markmap-skills: cannot read .antigravity-plugin/plugin.json", result.stdout)


if __name__ == "__main__":
    unittest.main()
