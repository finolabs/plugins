#!/usr/bin/env python3
"""Check that the Claude Code and Codex catalogs list the same plugins.

Each plugin appears once in each catalog, in the same order, from the same
GitHub repository. With --remote, also fetch each repository's plugin
manifests and confirm their `name` matches the catalog entry. Every source
must belong to an owner in OWNERS, so a catalog edit cannot point a plugin at
a look-alike fork. Pass a repository root as the first argument to check
another copy of the catalogs (the tests do).
"""

import json
import re
import sys
import urllib.request
from pathlib import Path

OWNERS = {"fioenix", "finolabs"}  # GitHub owners whose repositories may be listed

args = [a for a in sys.argv[1:] if not a.startswith("--")]
root = Path(args[0]) if args else Path(__file__).resolve().parent.parent
claude = json.loads((root / ".claude-plugin/marketplace.json").read_text())
codex = json.loads((root / ".agents/plugins/marketplace.json").read_text())
problems = []


def repo_of_claude(entry):
    src = entry.get("source")
    return src.get("repo") if isinstance(src, dict) and src.get("source") == "github" else None


def repo_of_codex(entry):
    src = entry.get("source")
    url = src.get("url", "") if isinstance(src, dict) and src.get("source") == "url" else ""
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
    elif not re.fullmatch(r"[A-Za-z0-9-]+/[A-Za-z0-9_.-]+", ra) or ra.split("/")[1] in (".", ".."):
        problems.append(f"{a['name']}: source {ra} is not a plain owner/repository")
    elif ra.split("/")[0] not in OWNERS:
        problems.append(f"{a['name']}: source owner {ra.split('/')[0]} is not in OWNERS")

readme = root / "README.md"
if readme.exists():
    # The plugin table lists the catalog's plugins, in order, each linked to its repository.
    rows = re.findall(r"^\| \[([^\]]+)\]\(https://github\.com/([^)]+)\) \|", readme.read_text(), re.M)
    if [name for name, _ in rows] != claude_names:
        problems.append(f"README table lists {[name for name, _ in rows]}, catalogs list {claude_names}")
    for (name, repo), entry in zip(rows, claude["plugins"]):
        if repo != repo_of_claude(entry):
            problems.append(f"README table links {name} to {repo}, catalog to {repo_of_claude(entry)}")

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
