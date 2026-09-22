# Portable Codex configuration

This repository contains the small, reusable portion of my personal Codex setup:

- `AGENTS.md`: global engineering and model-routing guidance.
- `skills/tokenomics/`: implicit skill for cost-aware GPT-6 Luna → GPT-6 Sol → GPT-6 Astra routing.
- `pstack-models.md`: Poteto Mode's per-role model configuration, installed to `$env:USERPROFILE\.agents\pstack-models.md`.
- `install.ps1`: installs those files and applies four portable Codex preferences.

## Restore on Windows

Clone the repository, open PowerShell in its directory, and run:

```powershell
.\install.ps1
```

The installer targets `$env:CODEX_HOME` when set, otherwise `$env:USERPROFILE\.codex`. It backs up any replaced global guidance, configuration, or earlier routing-skill folder beneath `.codex\backups\tokenomics-<timestamp>`.

It also sets these portable top-level preferences in the existing `config.toml` without replacing machine-specific sections:

```toml
model = "gpt-6-sol"
model_reasoning_effort = "low"
personality = "pragmatic"
service_tier = "default"
```

Start a new Codex task after installation. A full application restart is normally unnecessary.

## Tokenomics routing

Tokenomics uses a simple “smallest capable model” rule. It does not automatically change the selected model; on a nontrivial task it may recommend a manual switch when another tier is clearly a better fit.

| Model | Use it for |
| --- | --- |
| GPT-6 Luna | Straightforward, bounded work: searching or reading files, summaries, mechanical edits, formatting, tests, well-scoped refactors, and simple implementations. Try it first when a possible escalation is still worthwhile. |
| GPT-6 Sol | Moderate ambiguity or judgment, planning and architecture, difficult debugging, security-sensitive reasoning, consequential review, and integrating delegated results. |
| GPT-6 Astra | Hardest end-to-end work, unusually long-horizon or cross-domain tasks, very large context, or work where avoiding multiple Sol passes justifies the higher cost. Astra is an exception tier, not the default. |

Prefer GPT-6 Luna → GPT-6 Sol → GPT-6 Astra. Astra is an exception, not a routine third worker. Do not delegate or switch for a trivial task when context or switch overhead costs more than it saves. If Luna is clearly mismatched, move to Sol rather than retrying it repeatedly. Use Astra only when Sol is struggling or the stakes justify its higher cost.

Use `$tokenomics` when you specifically want a fresh routing assessment, such as after a task’s scope changes. You do not need to invoke it on every task: the global `AGENTS.md` contains the same routing checkpoint.

When Poteto Mode is active in Codex, its harness instructions read `~/.agents/pstack-models.md` when present. That file assigns models to Poteto agent roles and overrides its defaults. `install.ps1` copies this repository's `pstack-models.md` to `$env:USERPROFILE\.agents\pstack-models.md`, even when `CODEX_HOME` points elsewhere.

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
