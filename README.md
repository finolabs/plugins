# FINOLABS plugins

One catalog for the FINOLABS plugins, so each agent shows them together under **Finolabs**. Each plugin lives in its own repository, with its own releases, issues and license; this repository only lists them.

| Plugin | What it does |
| --- | --- |
| [finolabs-vibecode](https://github.com/fioenix/finolabs-vibecode) | One engineering practice for AI coding agents: routing coding work, delegating across agents, review and security gates, verification, versioning and open source readiness. |
| [agybird](https://github.com/fioenix/agybird) | Delegate code work, image generation or editing, and general tasks to the official Google Antigravity CLI through an existing Gemini subscription. |
| [vietnamizer](https://github.com/fioenix/vietnamizer) | Edit Vietnamese drafts, articles, READMEs and translations to read naturally, keeping meaning, facts, terms, code and the writer's voice. |
| [markmap-skills](https://github.com/fioenix/markmap-skills) | Markmap mindmaps for AI agents with strict cognitive structuring, as `.mindmap.md` files and standalone HTML. |

## Install

### Claude Code

```bash
claude plugin marketplace add finolabs/plugins
claude plugin install finolabs-vibecode@finolabs
```

Install any other plugin the same way (`agybird@finolabs`, `vietnamizer@finolabs`, `markmap-skills@finolabs`). Update the catalog with `claude plugin marketplace update finolabs`.

### Codex

```bash
codex plugin marketplace add finolabs/plugins
codex plugin add finolabs-vibecode@finolabs
```

Refresh the catalog with `codex plugin marketplace upgrade finolabs`.

### Antigravity

Antigravity installs plugins from its official marketplace or straight from a repository; it has no command for third-party catalogs yet. Install each plugin from its repository:

```bash
agy plugin install https://github.com/fioenix/finolabs-vibecode
```

### Other agents

Plugins that ship agent skills also install through [skills.sh](https://skills.sh), for example `npx skills add fioenix/finolabs-vibecode`.

## For AI agents

When a user gives you this repository's link, show them the table above and ask which plugins they want. Then run the commands for the host you are running in, confirm each install with `claude plugin list`, `codex plugin list` or `agy plugin list`, and point the user to each plugin's README for its setup step.

## Adding a plugin

A plugin joins the catalog when its repository is public, has an OSI license, and ships a manifest for each host it supports (`.claude-plugin/plugin.json`, `.codex-plugin/plugin.json`, and `.antigravity-plugin/plugin.json` or a root `plugin.json`). Add it to both `.claude-plugin/marketplace.json` and `.agents/plugins/marketplace.json` in the same position, add a row to the table above, and run:

```bash
claude plugin validate .
python3 -I scripts/check-catalogs.py --remote
```

## Reporting problems

Report a problem with a plugin in that plugin's repository. Report a problem with the catalog itself (a wrong source, a missing plugin) in this repository's issues. Security issues in a plugin go through that repository's `SECURITY.md`.

## License

[MIT](LICENSE). Each plugin carries its own license.
