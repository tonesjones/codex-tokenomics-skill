---
name: tokenomics
description: Execute efficient model routing in Codex. Delegate worthwhile bounded work to Luna, review and escalate in Sol, and verify the model and outcome. Includes optional portable cost estimates and usage logging.
---

# Tokenomics

Keep Sol 6.1 responsible for planning, orchestration, integration, and final review. Use a child model only when its bounded work repays the full handoff and review cost. A router recommendation alone is not completion.

## Choose the work

At one early planning checkpoint, assess the remaining work. Keep short or tightly coupled tasks in Sol. Do not run a routing script for obvious stay decisions or recommend routine top-level model switches. Staying on Sol may preserve cached input; cache eligibility and actual savings require measurement.

For substantial independent work, identify a compact deliverable suitable for Luna, such as collecting source evidence, inspecting files, mechanical edits, or running a defined test suite. Keep interpretation, architecture, difficult debugging, security decisions, integration, and final judgment with Sol. Assess the actual deliverable, not isolated words in the prompt. A mixed task may have a bounded collection step worth delegating even when the overall task needs Sol.

Check available models and use the observed active model. Use `gpt-6-luna` for bounded cheap-tier work and `gpt-6.1-sol` for task ownership and final judgment. GPT-6 Sol remains a recognized legacy capability alias; its prices are not inferred. Never pretend an unknown model is Sol. Choose Sol effort separately: low for routine work, medium for normal planning and integration, high for difficult reasoning or consequential review. Use runtime controls when available; this skill cannot set the current chat's model or effort itself.

For a plausible handoff, run the adjacent `tokenomics_router.py` once with the actual model, scope, independence, and your assessed task type:

```powershell
python "$env:USERPROFILE\.codex\skills\tokenomics\tokenomics_router.py" --current-model gpt-6.1-sol --work-scope substantial --independent --task-type source_collection "Collect source evidence and report gaps; leave interpretation to the parent"
```

Accepted cheap task types are `format`, `search`, `summary`, `source_collection`, `mechanical_edit`, and `test` when the actual deliverable is low ambiguity. Standard types include `architecture`, `security`, `hard_debugging`, `integration`, `planning`, and `design`. Unknown tasks default to standard. Assess task difficulty independently of its label. Do not rephrase repeatedly to obtain a desired route.

The router can return `stay`, `delegate`, or `request_approval` for Astra. Without prices, a Luna recommendation is qualitative; no dollar savings are established. With prices, compare future Sol work against child execution plus Sol handoff and review; judge likely recovery work separately. The default 15% savings margin is a rough allowance for estimate uncertainty, not a measured failure rate. Cached input rates and cache hits must be measured or treated as unknown. Unknown pricing is not itself a reason to reject a substantial independent Luna task. If the script is unavailable, apply the same criteria directly and disclose the fallback.

## Execute and finish

1. On `stay`, do the work in the active model and finish the user's task.
2. On `delegate`, use the available collaboration tool to spawn the recommended child when authorized by the user and runtime. Use an explicit model override and a self-contained prompt or small context fork. Include the deliverable, relevant paths, evidence needed, acceptance criteria, stop conditions, and boundaries. Avoid shared file writes between parent and child.
3. Continue independent parent work, then wait for the child. A spawned child or recommendation is not the final result.
4. Verify the child's model from session/runtime metadata when accessible. Record requested and observed models separately. If metadata is unavailable, mark the model unverified. If the override was ignored, do not repeat the same unsupported attempt or claim cheaper execution.
5. Review the deliverable against source evidence or run the affected behavior. If Luna's result is inadequate, continue in Sol. Avoid repeated Luna retries. For `request_approval`, finish the available Sol investigation, present the exact Astra question and scope, and wait for explicit human approval before spawning or switching to Astra. Approval for one question does not cover another.
6. Integrate the usable work, run appropriate verification, and complete the original task. If delegation is unavailable or prohibited, continue locally and briefly explain that limitation.

Report a short routing note with the action, requested/observed child model when relevant, whether its work was usable or escalated, and any measured usage. Do not add a long routing report to every answer. Successful task completion and successful cheaper-model execution are separate facts.

## Optional estimates and records

The adjacent Python module is also portable. `route_task(task, context=None, config=None)` returns the action, candidate, estimates, and reason; the caller executes it. `context['assessment']` accepts `task_type`, `complexity`, `confidence`, and `expected_output_bucket`. `--task-type` is the simple CLI equivalent. Models, aliases, prices, output buckets, and overhead are configurable. No prices are supplied by default.

Use `record_result(decision, actual_usage, success, config)` with a configured `log_path` for local JSONL. Include requested and observed models, result usability, escalation, and provider-reported tokens/cost when available. Omit unavailable measurements. `summarize_usage(path)` summarizes records; savings require an observed baseline and actual costs. Do not equate API dollar estimates with ChatGPT plan usage or claim measured savings from a recommendation.

Only use cost estimation when it helps the decision. Task-description length is not the full execution context; supply remaining Sol input with `input_tokens` and compact child input with `child_input_tokens` when known. `parent_remaining_input_tokens` covers Sol input still needed after a handoff. Use `stay_cached_input_tokens` or `child_cached_input_tokens` only with evidence for cache hits and a configured `cached_input_per_million` price. Count future cost only. Child overhead defaults are guesses, not measurements. Cached input still uses context space. Do not assume a top-level switch always destroys cache or staying always hits it. Keep optional classifier integrations, including Jev, out of the normal flow until recorded outcomes justify them.

## Installation

Keep one active `tokenomics` folder. Preserve backups outside discoverable skills directories. Do not reinstall unrelated global settings merely to update this skill. New chats load updated skill instructions; existing chats may retain earlier instructions.
