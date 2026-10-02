# Portable Codex configuration

This repository contains the small, reusable portion of my personal Codex setup:

- `AGENTS.md`: global engineering and model-routing guidance.
- `skills/tokenomics/`: a delegation, review, and escalation workflow plus an optional dependency-free router/cost estimator. Its default tier mapping is GPT-6 Luna → GPT-6 Sol → GPT-6 Astra, but projects can supply their own model IDs and current prices.
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
model = "gpt-6.1-sol"
model_reasoning_effort = "low"
personality = "pragmatic"
service_tier = "default"
```

Start a new Codex task after installation. A full application restart is normally unnecessary.

## Tokenomics routing

Tokenomics keeps GPT-6.1 Sol responsible for a substantial task from planning through final review. It considers a bounded Luna child when its work is independent and the handoff pays. A router recommendation does not change the selected model or reasoning effort.

| Model | Use it for |
| --- | --- |
| GPT-6 Luna | Bounded, low-ambiguity collection, mechanical changes, defined tests, and well-scoped implementation when the handoff is worthwhile. |
| GPT-6.1 Sol | Session ownership, planning, architecture, difficult debugging, integration, and final review. Start at low effort for routine work, medium for normal planning, and high for difficult reasoning, changing runtime effort only when supported and useful. |
| GPT-6 Astra | An exceptional consultation about a specific unresolved problem, after explicit human approval for that use. Sol integrates and reviews its result. |

Do small or coupled work in Sol. A new model may need context reconstruction, while continuing in Sol may reuse cached input; neither cache behavior nor savings are guaranteed. Compare the future Sol work against Luna execution plus Sol preparation, review, and possible recovery. A difficult task does not become suitable for Luna just because it is labeled “test.” Return an inadequate Luna result to Sol rather than repeatedly retrying Luna.

Use `$tokenomics` when you specifically want a fresh routing assessment, such as after a task’s scope changes. You do not need to invoke it on every task: the global `AGENTS.md` contains the same routing checkpoint.

For a calling project that needs a programmatic decision, copy `skills/tokenomics/tokenomics_router.py` and call `route_task(task, context=None, config=None)`. It returns `stay`, `delegate`, or `request_approval` for Astra. The caller must verify authorization immediately before any Astra dispatch. Unknown prices remain `None`. Estimates are useful only with realistic remaining Sol work, compact child input, and measured cache behavior. `record_result` can write local JSONL usage; `summarize_usage` provides feedback. See the skill's `SKILL.md` for a minimal example and optional Jev classifier boundary.

In Codex, the global guidance calls `$tokenomics` at the planning checkpoint for substantial, independent, bounded work. When prices are unavailable, it may recommend Luna qualitatively while marking dollar savings unverified. Sol performs and verifies the handoff and retains final responsibility.

### When to add Jev

Start with the local classifier and log the actual results. Jev becomes useful when ambiguous task descriptions repeatedly cause the local rules to choose a tier that is too weak or unnecessarily strong, and there are enough routed tasks for a classification call to repay its cost and latency. Review a few dozen representative logged tasks (20–50 is a starting sample, not a proven threshold), compare Jev's classification against the local rule on those same tasks, and enable it only if the decisions improve.

Jev can supply task type, complexity, expected output size, and confidence; Tokenomics still chooses the model and calculates dollars. A project can pass a Jev-backed `classifier` callable without changing the public `route_task` call. The current repository includes that callable boundary **but no Jev HTTP adapter or live Jev verification**. The tests use fixed signals and a simulated classifier failure, so they run without a TypeSafe API key. A live integration would need the key, a checked request/response mapping, and calibration against your own tasks. If that classifier fails, the local fallback continues to route.

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

The skill accepts an agent-assessed task type through `--task-type` and uses GPT-6.1 Sol by default and recognizes legacy GPT-6 Sol capability without borrowing model prices. Update only the skill folder to preserve unrelated global settings. Keep backups outside discoverable skills directories.
