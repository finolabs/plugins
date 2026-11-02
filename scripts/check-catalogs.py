#!/usr/bin/env python3
"""Check that the Claude Code and Codex catalogs list the same plugins.

Each plugin appears once in each catalog, in the same order, from the same
GitHub repository. With --remote, also fetch each repository's plugin
manifests and confirm their `name` matches the catalog entry.
"""

import json
import sys
import urllib.request
from pathlib import Path

root = Path(__file__).resolve().parent.parent
claude = json.loads((root / ".claude-plugin/marketplace.json").read_text())
codex = json.loads((root / ".agents/plugins/marketplace.json").read_text())
problems = []


def repo_of_claude(entry):
    src = entry["source"]
    return src.get("repo") if isinstance(src, dict) and src.get("source") == "github" else None


def repo_of_codex(entry):
    url = entry["source"].get("url", "")
    prefix, suffix = "https://github.com/", ".git"
    return url[len(prefix):-len(suffix)] if url.startswith(prefix) and url.endswith(suffix) else None


claude_names = [p["name"] for p in claude["plugins"]]
codex_names = [p["name"] for p in codex["plugins"]]
if claude["name"] != codex["name"]:
    problems.append(f"catalog names differ: {claude['name']} and {codex['name']}")
if claude_names != codex_names:
    problems.append(f"plugin lists differ: {claude_names} and {codex_names}")
if len(set(claude_names)) != len(claude_names):
    problems.append("a plugin is listed twice")
for a, b in zip(claude["plugins"], codex["plugins"]):
    ra, rb = repo_of_claude(a), repo_of_codex(b)
    if not ra or ra != rb:
        problems.append(f"{a['name']}: sources differ or are not GitHub repositories ({ra}, {rb})")

if "--remote" in sys.argv:
    for entry in claude["plugins"]:
        repo = repo_of_claude(entry)
        for manifest in (".claude-plugin/plugin.json", ".codex-plugin/plugin.json"):
            url = f"https://raw.githubusercontent.com/{repo}/HEAD/{manifest}"
            try:
                with urllib.request.urlopen(url, timeout=20) as response:
                    name = json.load(response).get("name")
            except Exception as error:  # noqa: BLE001 - report any fetch or parse failure
                problems.append(f"{entry['name']}: cannot read {manifest} ({error.__class__.__name__})")
                continue
            if name != entry["name"]:
                problems.append(f"{entry['name']}: {manifest} names the plugin {name}")

print("\n".join(problems) or f"catalogs ok ({len(claude_names)} plugins)")
sys.exit(1 if problems else 0)
