# Portable Codex configuration

This repository contains the small, reusable portion of my personal Codex setup:

- `AGENTS.md`: global engineering and model-routing guidance.
- `skills/tokenomics/`: implicit routing guidance plus a dependency-free portable router/cost estimator. Its default tier mapping is GPT-6 Luna → GPT-6 Sol → GPT-6 Astra, but projects can supply their own model IDs and current prices.
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

For a calling project that needs a programmatic decision, copy `skills/tokenomics/tokenomics_router.py` and call `route_task(task, context=None, config=None)`. It compares staying in the current model with child tiers, including configurable context rebuild and file-read tokens, and returns `action: stay` or `delegate` plus cost estimates for every option. Unknown prices remain `None`. The caller executes the decision; `record_result` can write local JSONL usage, and `summarize_usage` gives a compact feedback loop. See the skill's `SKILL.md` for a minimal example and optional Jev classifier boundary.

In Codex, the global guidance calls `$tokenomics` at the planning checkpoint for substantial, independent, bounded work. The skill runs the router with the active model and a short task summary. When prices are unavailable, it may recommend a cheap child for such work based on capability and scope, clearly marking dollar savings as unverified. Brief or tightly coupled work stays in the current model. The router prints a recommendation; Codex or the calling project still performs and verifies any model handoff.

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
