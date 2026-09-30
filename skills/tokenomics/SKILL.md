---
name: tokenomics
description: Execute efficient model routing in Codex. Delegate worthwhile bounded work to Luna, review and escalate in Sol, and verify the model and outcome. Includes optional portable cost estimates and usage logging.
---

# Tokenomics

Complete the user's task using the smallest capable model when the handoff is worthwhile. This skill is an execution workflow. A router recommendation alone is not completion.

## Choose the work

At one early planning checkpoint, assess the remaining work. Keep short or tightly coupled tasks in the active model. Do not run a routing script for obvious stay decisions.

For substantial independent work, identify a compact deliverable suitable for Luna, such as collecting source evidence, inspecting files, mechanical edits, or running a defined test suite. Keep interpretation, architecture, difficult debugging, security decisions, integration, and final judgment with Sol. Assess the actual deliverable, not isolated words in the prompt. A mixed task may have a bounded collection step worth delegating even when the overall task needs Sol.

Check available models and use the observed active model. Use `gpt-6-luna` for the cheap tier and `gpt-6.1-sol` for the standard tier and Sol escalation. GPT-6 Sol remains a recognized legacy capability alias; its prices are not inferred. Never pretend an unknown model is Sol. Recommend a manual top-level switch only when a nontrivial task is clearly mismatched; a skill cannot change the current chat's model itself.

For a plausible handoff, run the adjacent `tokenomics_router.py` once with the actual model, scope, independence, and your assessed task type:

```powershell
python "$env:USERPROFILE\.codex\skills\tokenomics\tokenomics_router.py" --current-model gpt-6.1-sol --work-scope substantial --independent --task-type source_collection "Collect source evidence and report gaps; leave interpretation to the parent"
```

Accepted cheap task types are `format`, `search`, `summary`, `source_collection`, `mechanical_edit`, and `test`. Standard types include `architecture`, `security`, `hard_debugging`, `integration`, `planning`, and `design`. Unknown tasks default to standard. The agent assessment overrides the conservative keyword fallback. Do not rephrase repeatedly to obtain a desired route.

The router returns `stay` or `delegate`. Without prices, a Luna recommendation is qualitative; no dollar savings are established. With prices, the comparison includes handoff overhead. Unknown pricing is not itself a reason to reject a substantial independent Luna task. If the script is unavailable, apply the same criteria directly and disclose the fallback.

## Execute and finish

1. On `stay`, do the work in the active model and finish the user's task.
2. On `delegate`, use the available collaboration tool to spawn the recommended child. Explicit invocation of this skill requests delegation when these criteria are met; implicit use remains subject to the user's and runtime's delegation rules. Use an explicit model override and a self-contained prompt or small context fork. Include the deliverable, relevant paths, evidence needed, and boundaries. Avoid shared file writes between parent and child.
3. Continue independent parent work, then wait for the child. A spawned child or recommendation is not the final result.
4. Verify the child's model from session/runtime metadata when accessible. Record requested and observed models separately. If metadata is unavailable, mark the model unverified. If the override was ignored, do not repeat the same unsupported attempt or claim cheaper execution.
5. Review the deliverable against source evidence or run the affected behavior. If Luna's result is inadequate, continue in Sol or make one Sol handoff with the useful evidence. Avoid repeated Luna retries. Use Astra only for exceptional difficulty and when the user's authorization permits it.
6. Integrate the usable work, run appropriate verification, and complete the original task. If delegation is unavailable or prohibited, continue locally and briefly explain that limitation.

Report a short routing note with the action, requested/observed child model when relevant, whether its work was usable or escalated, and any measured usage. Do not add a long routing report to every answer. Successful task completion and successful cheaper-model execution are separate facts.

## Optional estimates and records

The adjacent Python module is also portable. `route_task(task, context=None, config=None)` returns the action, candidate, estimates, and reason; the caller executes it. `context['assessment']` accepts `task_type`, `complexity`, `confidence`, and `expected_output_bucket`. `--task-type` is the simple CLI equivalent. Models, aliases, prices, output buckets, and overhead are configurable. No prices are supplied by default.

Use `record_result(decision, actual_usage, success, config)` with a configured `log_path` for local JSONL. Include requested and observed models, result usability, escalation, and provider-reported tokens/cost when available. Omit unavailable measurements. `summarize_usage(path)` summarizes records; savings require an observed baseline and actual costs. Do not equate API dollar estimates with ChatGPT plan usage or claim measured savings from a recommendation.

Only use cost estimation when it helps the decision. Task-description length is not the full execution context; supply `input_tokens` when known. Child overhead defaults are guesses, not measurements. Keep optional classifier integrations, including Jev, out of the normal flow until recorded outcomes justify them.

## Installation

Keep one active `tokenomics` folder. Preserve backups outside discoverable skills directories. Do not reinstall unrelated global settings merely to update this skill. New chats load updated skill instructions; existing chats may retain earlier instructions.
