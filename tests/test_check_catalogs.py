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
        self.assertIn("source owner 'evil' is not in OWNERS", result.stdout)

    def test_remote_skips_a_source_that_already_failed(self):
        self.edit(self.claude, lambda d: d["plugins"][0]["source"].update(repo="evil/finolabs-vibecode"))
        self.edit(self.codex, lambda d: d["plugins"][0]["source"].update(url="https://github.com/evil/finolabs-vibecode.git"))
        empty = tempfile.TemporaryDirectory()
        self.addCleanup(empty.cleanup)
        # Both bases point at an empty directory, so no request reaches GitHub: pinned entries fail at
        # the tag check and unpinned ones at the manifest read, the same way on any network.
        env = {"CATALOG_RAW_BASE": Path(empty.name).as_uri(), "CATALOG_API_BASE": Path(empty.name).as_uri(),
               "PATH": "/usr/bin:/bin"}
        result = subprocess.run([sys.executable, "-I", str(ROOT / "scripts/check-catalogs.py"), str(self.root), "--remote"],
                                capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 1)
        self.assertIn("source owner 'evil' is not in OWNERS", result.stdout)
        self.assertNotIn("'finolabs-vibecode': cannot", result.stdout)
        self.assertIn("'agybird': cannot", result.stdout)

    def test_remote_does_not_fetch_an_entry_past_the_shorter_catalog(self):
        self.edit(self.claude, lambda d: d["plugins"][-1]["source"].update(repo="evil/x"))
        self.edit(self.codex, lambda d: d["plugins"].pop())
        empty = tempfile.TemporaryDirectory()
        self.addCleanup(empty.cleanup)
        env = {"CATALOG_RAW_BASE": Path(empty.name).as_uri(), "CATALOG_API_BASE": Path(empty.name).as_uri(),
               "PATH": "/usr/bin:/bin"}
        result = subprocess.run([sys.executable, "-I", str(ROOT / "scripts/check-catalogs.py"), str(self.root), "--remote"],
                                capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 1)
        self.assertIn("plugin lists differ", result.stdout)
        self.assertNotIn("'markmap-skills': cannot read", result.stdout)

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

    def test_description_length_limits_are_inclusive(self):
        for length, accepted in [(119, False), (120, True), (160, True), (161, False)]:
            with self.subTest(length=length):
                self.edit(self.claude, lambda d: d["plugins"][0].update(description="x" * length))
                stdout = self.check().stdout
                self.assertEqual("expected 120-160" not in stdout, accepted, stdout)

    def test_entry_without_keywords_fails(self):
        self.edit(self.claude, lambda d: d["plugins"][0].pop("keywords"))
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("'finolabs-vibecode': no keywords", result.stdout)

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
        self.root = self.base / "catalog"
        for name in (".claude-plugin", ".agents"):
            shutil.copytree(ROOT / name, self.root / name)
        shutil.copy(ROOT / "README.md", self.root / "README.md")
        self.catalog_path = self.root / ".claude-plugin/marketplace.json"
        for entry in catalog["plugins"]:
            entry["source"].pop("ref", None)
        self.catalog_path.write_text(json.dumps(catalog))

    def pin(self, ref="v1", kind="commit", on_branch=True):
        entry = self.catalog["plugins"][0]
        entry["source"]["ref"] = ref
        self.catalog_path.write_text(json.dumps(self.catalog))
        repo = entry["source"]["repo"]
        api = self.base / "api/repos" / repo
        (api / "git/ref/tags").mkdir(parents=True, exist_ok=True)
        (api / "git/ref/tags" / ref).write_text(json.dumps({"ref": "refs/tags/" + ref, "object": {"type": kind, "sha": "abc123"}}))
        (api / "compare").mkdir(exist_ok=True)
        (api / "compare/abc123...def456").write_text(json.dumps({"status": "ahead" if on_branch else "diverged"}))
        (api / "commits").mkdir(exist_ok=True)
        (api / "commits/main").write_text(json.dumps({"sha": "def456"}))
        (api / "repository").write_text(json.dumps({"default_branch": "main"}))
        shutil.copytree(self.base / repo / "HEAD", self.base / repo / "abc123", dirs_exist_ok=True)

    def tearDown(self):
        self.dir.cleanup()

    def check(self):
        env = {"CATALOG_RAW_BASE": self.base.as_uri(), "CATALOG_API_BASE": (self.base / "api").as_uri(), "PATH": "/usr/bin:/bin"}
        return subprocess.run([sys.executable, "-I", str(ROOT / "scripts/check-catalogs.py"), str(self.root), "--remote"],
                              capture_output=True, text=True, env=env)

    def test_missing_tag_fails(self):
        self.pin()
        (self.base / "api/repos/finolabs/finolabs-vibecode/git/ref/tags/v1").unlink()
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("'v1'", result.stdout)

    def test_branch_name_is_not_a_tag(self):
        self.pin("main")
        (self.base / "api/repos/finolabs/finolabs-vibecode/git/ref/tags/main").unlink()
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stdout)

    def test_commit_outside_default_branch_fails(self):
        self.pin(on_branch=False)
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stdout)

    def test_drift_at_tag_fails_even_if_head_matches(self):
        self.pin()
        path = self.base / "finolabs/finolabs-vibecode/abc123/.codex-plugin/plugin.json"
        data = json.loads(path.read_text())
        data["description"] = "different"
        path.write_text(json.dumps(data))
        result = self.check()
        self.assertEqual(result.returncode, 1, result.stdout)
        self.assertIn("description differs from the catalog entry", result.stdout)

    def test_annotated_tag_is_peeled(self):
        self.pin(kind="tag")
        api = self.base / "api/repos/finolabs/finolabs-vibecode/git/tags"
        api.mkdir(parents=True)
        (api / "abc123").write_text(json.dumps({"object": {"type": "commit", "sha": "abc123"}}))
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_valid_pin_passes(self):
        self.pin()
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_without_ref_reads_head(self):
        self.pin()
        self.catalog["plugins"][0]["source"].pop("ref")
        self.catalog_path.write_text(json.dumps(self.catalog))
        shutil.rmtree(self.base / "finolabs/finolabs-vibecode/abc123")
        result = self.check()
        self.assertEqual(result.returncode, 0, result.stdout)

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
        self.assertIn("'agybird': .antigravity-plugin/plugin.json description differs from the catalog entry", result.stdout)

    def test_manifest_keyword_drift_fails(self):
        path = self.base / "finolabs/vietnamizer/HEAD/.codex-plugin/plugin.json"
        data = json.loads(path.read_text())
        data["keywords"] = data["keywords"][:-1]
        path.write_text(json.dumps(data))
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("'vietnamizer': .codex-plugin/plugin.json keywords differs from the catalog entry", result.stdout)

    def test_manifest_naming_another_plugin_fails(self):
        path = self.base / "finolabs/agybird/HEAD/.claude-plugin/plugin.json"
        data = json.loads(path.read_text())
        data["name"] = "agybird-fork"
        path.write_text(json.dumps(data))
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("'agybird': .claude-plugin/plugin.json names the plugin 'agybird-fork'", result.stdout)

    def test_manifest_that_is_not_an_object_fails_without_crashing(self):
        (self.base / "finolabs/agybird/HEAD/.codex-plugin/plugin.json").write_text("[1]")
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("'agybird': .codex-plugin/plugin.json is not a JSON object", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_unsupported_base_scheme_is_refused(self):
        env = {"CATALOG_RAW_BASE": "ftp://example.invalid", "PATH": "/usr/bin:/bin"}
        result = subprocess.run([sys.executable, "-I", str(ROOT / "scripts/check-catalogs.py"), "--remote"],
                                capture_output=True, text=True, env=env)
        self.assertEqual(result.returncode, 1)
        self.assertIn("must start with https:// or file://", result.stderr)

    def test_missing_antigravity_manifest_fails(self):
        (self.base / "finolabs/markmap-skills/HEAD/.antigravity-plugin/plugin.json").unlink()
        result = self.check()
        self.assertEqual(result.returncode, 1)
        self.assertIn("'markmap-skills': cannot read .antigravity-plugin/plugin.json", result.stdout)


if __name__ == "__main__":
    unittest.main()
