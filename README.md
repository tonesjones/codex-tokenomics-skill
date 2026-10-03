# Portable Codex configuration

This repository contains the small, reusable portion of my personal Codex setup:

- `AGENTS.md`: global engineering and model-routing guidance.
- `skills/tokenomics/`: a dependency-free delegation workflow and selective subscription usage audit. Sol 6.1 owns the task; Luna handles worthwhile bounded work; Astra requires explicit approval.
- `pstack-models.md`: Poteto Mode's per-role model configuration, installed to `$env:USERPROFILE\.agents\pstack-models.md`.
- `install.ps1`: restores the full configuration and applies four portable Codex preferences.
- `install_skill.py`: updates only Tokenomics on Windows, macOS or Linux.

## Restore on Windows

Clone the repository, open PowerShell in its directory, and run:

```powershell
.\install.ps1
```

The installer targets `$env:CODEX_HOME` when set, otherwise `$env:USERPROFILE\.codex`. It backs up any replaced global guidance, configuration, or earlier routing-skill folder beneath `.codex\backups\tokenomics-<timestamp>`.

It also sets these portable top-level preferences in the existing `config.toml` without replacing machine-specific sections:

```toml
model = "gpt-6.1-sol"
model_reasoning_effort = "low"
personality = "pragmatic"
service_tier = "default"
```

Start a new Codex task after installation. A full application restart is normally unnecessary.

## Update only the skill

The cross-platform installer changes only Tokenomics, backs up an existing installation, and verifies file hashes. It does not change global guidance, model settings or Poteto roles.

```powershell
python install_skill.py
# Or update an explicit existing location:
python install_skill.py --target "$env:USERPROFILE\.codex\skills\tokenomics"
```

For a cloud or local project, install into its repository skill-discovery location:

```bash
python3 /path/to/codex-tokenomics-skill/install_skill.py --repo-root /path/to/project
```

Run this once in environment setup, or commit the installed `.agents/skills/tokenomics` files in the target project. Updating the Windows installation does not update cloud environments. The current repository keeps its maintained source under `skills/tokenomics`.

Codex discovers repository skills under `.agents/skills` and user skills under `~/.agents/skills`. The installer preserves this project's existing legacy `~/.codex/skills/tokenomics` installation when appropriate. See [official skill-discovery guidance](https://learn.chatgpt.com/docs/build-skills). Newly loaded sessions can use the updated skill; restart Codex if it does not appear.

Routing and outcome records work on local and cloud sessions. Runtime measurement works only when the environment exposes explicitly associated session metadata. For cloud sessions without accessible logs, record the actual runtime session ID, `environment="cloud"` and `path=None`; usage stays unknown. This path has fixture coverage. No live cloud token-export access or cross-account installation is claimed.

## Tokenomics routing

Tokenomics keeps GPT-6.1 Sol responsible for a substantial task from planning through final review. It considers a bounded Luna child when its work is independent and the handoff pays. A router recommendation does not change the selected model or reasoning effort.

| Model | Use it for |
| --- | --- |
| GPT-6 Luna | Bounded, low-ambiguity collection, mechanical changes, defined tests, and well-scoped implementation when the handoff is worthwhile. |
| GPT-6.1 Sol | Session ownership, planning, architecture, difficult debugging, integration, and final review. Start at low effort for routine work, medium for normal planning, and high for difficult reasoning, changing runtime effort only when supported and useful. |
| GPT-6 Astra | An exceptional consultation about a specific unresolved problem, after explicit human approval for that use. Sol integrates and reviews its result. |

Do small or coupled work in Sol. A new model may need context reconstruction, while continuing in Sol may reuse cached input; neither cache behavior nor savings are guaranteed. Compare the future Sol work against Luna execution plus Sol preparation, review, and possible recovery. A difficult task does not become suitable for Luna just because it is labeled “test.” Return an inadequate Luna result to Sol rather than repeatedly retrying Luna.

Use `$tokenomics` when you specifically want a fresh routing assessment, such as after a task’s scope changes. You do not need to invoke it on every task: the global `AGENTS.md` contains the same routing checkpoint.

The portable `route_task(task, context=None, config=None)` interface returns `stay`, `delegate`, or `request_approval`. Supply the observed current model; missing identity stays unresolved. Routing is qualitative. No pricing, credits, billing integrations or dashboard are used.

`record_result` and `summarize_usage` share stable decision IDs and preserve the original routing fields. Child usability and full-task acceptance are separate. Retrospective checkpoints are explicit, and legacy records without IDs stay unpaired. The `success` argument remains a full-task acceptance alias; arbitrary usage dictionaries no longer overwrite decision metadata.

For a selective audit, `associate_sessions` records only explicitly named parent and child sessions. `collect_usage` reads their runtime metadata and cumulative counters, including cache input, observed model and effort. Include handoff, review, required review children, retries and recovery. Repeated counters and repeated audits do not double-count. Missing baselines, ambiguous resets, open intervals and absent fields remain unknown. The collector stores metadata, not chat text. See [the skill instructions](skills/tokenomics/SKILL.md) for examples and interval requirements.

```powershell
python skills/tokenomics/tokenomics_router.py --log .tokenomics/decisions.jsonl --collect DECISION_ID
python skills/tokenomics/tokenomics_router.py --log .tokenomics/decisions.jsonl --summary
python -m unittest discover -s tests -v
```

Audits run when requested, not each turn. `record_comparison` records occasional equivalent Sol-only and Sol-plus-Luna pairs with the same acceptance checks, coordination, review and recovery. Reports show token consumption by model and time per accepted result, with effort/cache conditions. They never claim exact subscription allowance savings. No baseline means savings are unknown. Optional account snapshots are account-wide and may include concurrent chats or resets.

Tests use fixtures. [CHECKPOINT.md](CHECKPOINT.md) records separate live-session verification and the local review checkpoint. Runtime JSONL and snapshots stay ignored by Git.

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

The skill accepts an agent-assessed task type through `--task-type` and uses GPT-6.1 Sol by default and recognizes legacy GPT-6 Sol capability. Update only the skill folder to preserve unrelated global settings. Keep backups outside discoverable skills directories.
