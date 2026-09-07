# Portable Codex configuration

This repository contains the small, reusable portion of my personal Codex setup:

- `AGENTS.md`: global engineering and model-routing guidance.
- `skills/tokenomics/`: implicit skill for cost-aware Luna → Terra → Sol routing.
- `install.ps1`: installs those files and applies four portable Codex preferences.

## Restore on Windows

Clone the repository, open PowerShell in its directory, and run:

```powershell
.\install.ps1
```

The installer targets `$env:CODEX_HOME` when set, otherwise `$env:USERPROFILE\.codex`. It backs up any replaced global guidance, configuration, or earlier routing-skill folder beneath `.codex\backups\tokenomics-<timestamp>`.

It also sets these portable top-level preferences in the existing `config.toml` without replacing machine-specific sections:

```toml
model = "gpt-5.6-sol"
model_reasoning_effort = "low"
personality = "pragmatic"
service_tier = "default"
```

Start a new Codex task after installation. A full application restart is normally unnecessary.

## Tokenomics routing

Tokenomics uses a simple “smallest capable model” rule. It does not automatically change the selected model; on a nontrivial task it may recommend a manual switch when another tier is clearly a better fit.

| Model | Use it for |
| --- | --- |
| Luna | Straightforward, bounded work: searching or reading files, summaries, mechanical edits, formatting, repetitive transformations, and simple implementations. |
| Terra | Moderate debugging, multi-file implementation, reviewing Luna-sized work, or moderate ambiguity and judgment. |
| Sol | Planning and architecture, difficult debugging, security-sensitive reasoning, consequential review, integrating delegated results, and genuinely ambiguous work. |
| Astra | Hardest end-to-end work, unusually long-horizon or cross-domain tasks, very large context, or work where avoiding multiple Sol passes justifies the higher cost. Astra is an exception tier, not the default. |

Prefer the escalation path Luna → Terra → Sol, with Astra as a selective exception above Sol. Do not delegate or switch for a trivial task when the context/switch overhead costs more than it saves. If a weaker model is clearly mismatched, move up one tier rather than retrying it repeatedly.

Use `$tokenomics` when you specifically want a fresh routing assessment, such as after a task’s scope changes. You do not need to invoke it on every task: the global `AGENTS.md` contains the same routing checkpoint.

## Rollback

Use ordinary Git history to select the desired configuration version, then rerun `install.ps1`. The installer’s timestamped backup provides a local pre-install copy when needed.

## Intentionally excluded

The allowlist-style `.gitignore` prevents accidental tracking of everything except the files named above. In particular, this repository excludes:

- `auth.json`, credentials, API keys, OAuth tokens, secrets, and MCP headers.
- Full `config.toml`, because it contains machine paths, plugin state, project trust records, connector settings, and environment-specific MCP configuration.
- Sessions, history, memories, databases, caches, logs, attachments, generated media, browser state, installation identifiers, and temporary state.
- Bundled/system skills, plugins, marketplaces, and downloaded packages.
- The custom `bd` skill and proprietary local documentation dependencies.

Do not weaken the `.gitignore` allowlist without reviewing every newly included file for credentials and machine-specific data.
