---
name: tokenomics
description: Keep Sol responsible for routing, delegation and review. Selectively audit observed Codex subscription usage and occasional equivalent task pairs.
metadata:
  version: "0.3.1"
  updated: "2026-10-03"
---

# Tokenomics

Keep GPT-6.1 Sol responsible from intake through final review. Use Luna only for substantial, independent, bounded work whose value exceeds preparing the handoff, rebuilding context, reviewing output and recovering from failure. Keep architecture, difficult debugging, security decisions, integration and final judgment in Sol. Astra requires explicit human approval for the specific question. This skill does not change the current model or effort.

## Route once when worthwhile

Do small or coupled work directly in Sol. Do not run the router, add a checkpoint or ask about routing for a trivial task. For substantial work, consider one concrete bounded deliverable. Keep it in Sol if it is too small, ambiguous or dependent on the parent's evolving work. Do not create a child to satisfy a quota. Assess difficulty independently of a label such as `test`.

Resolve the active model from trusted runtime context or the matching session's `turn_context.payload.model`. Never substitute a configured default or another chat's model. Unknown identity returns `needs_model_identity`; continue locally until resolved. Choose Sol effort separately, using runtime controls when available. Do not repeatedly change it without a reason.

For a plausible delegation, run the adjacent router once with the actual model and assessed scope. Use a short deliverable summary, never source code, prompts or credentials.

```powershell
python "$env:USERPROFILE\.codex\skills\tokenomics\tokenomics_router.py" --current-model gpt-6.1-sol --work-scope substantial --independent --task-type source_collection --log .tokenomics/decisions.jsonl "Collect bounded evidence for Sol review"
```

The router is qualitative. Token estimates are separate from observations and cannot establish subscription savings. `route_task(task, context=None, config=None)` keeps the portable interface. Each result has a `decision_id`; keep that result through execution. Custom model IDs and a local classifier remain supported. A classifier failure falls back locally. No network integration, pricing, credits or billing is used.

## Execute and capture evidence

1. On `stay`, finish locally. On `delegate`, use a supported explicit model override and a self-contained prompt or small context fork. Include the deliverable, evidence, acceptance checks and stop condition. Avoid shared file writes. If delegation is prohibited or unsupported, continue in Sol.
2. As part of the handoff, retain the parent session ID and the returned child session IDs. Record every related child, including nested children and reviews required by other skills. Distinguish `tokenomics`, `required_review` and `other` purposes and give a short reason. A required review does not prove Tokenomics routing helped.
3. Verify the observed child model using its associated session metadata. Requested model and observed model are separate. Mark inaccessible metadata unknown. Do not claim Luna execution from a spawn argument alone.
4. Review source evidence or run the relevant behavior, integrate usable output and finish the user's task. Return inadequate Luna work to Sol rather than repeatedly retrying Luna. Record `child_output_usable` separately from `task_accepted`. Use only `escalated` for escalation, with `True`, `False` or `None`. Retries and recovery are separate fields, unknown unless supported by runtime evidence or the parent's execution record.
5. Use the existing logger for the outcome and associations. The agent maintains these records; do not ask the user to do bookkeeping. Capture them when routing is actually used or a selective audit is requested. No extra checks or records are required on ordinary trivial tasks.

`record_result(decision, actual_usage, success=None, config=None)` keeps its call shape. `success` is the legacy argument for full-task acceptance. Record a checkpoint before an outcome when logging. Outcomes preserve the checkpoint's original model, tier, task type and deliverable; do not relabel a cheap-tier decision as standard after Sol recovery. `stage="checkpoint"` is excluded from completed results. Set `retrospective=True` for a checkpoint reconstructed after execution. Old records without IDs remain unpaired and excluded; never infer their missing linkage or acceptance.

```python
from tokenomics_router import record_result, associate_sessions
config = {"log_path": ".tokenomics/decisions.jsonl"}
# decision is the result already returned by route_task or the CLI.
# Save a checkpoint here only if the CLI did not already save it.
record_result(decision, {"stage": "checkpoint", "retrospective": False}, config=config)
associate_sessions(decision, sessions, config, all_children_accounted=True)
record_result(decision, {
    "child_output_usable": True, "task_accepted": True, "escalated": False,
    "requested_child_model": "gpt-6-luna", "observed_child_model": "gpt-6-luna",
    "retries": 0, "recovery": False,
}, config=config)
```

Use those booleans and counts only when the evidence supports them. Omit unknown fields. `all_children_accounted=True` requires checking the actual returned child list, including any children created by another skill. Otherwise leave it unknown.

## Selective measurement

Collect on request, at a useful review checkpoint, or when recording a selected comparison. Do not run an audit each turn, automatically duplicate work, launch benchmarks or schedule recurring jobs. The collector and summarizer are part of the existing module and use the same JSONL log.

Each entry in `sessions` is an explicit allowlist:

```python
sessions = [{
    "session_id": parent_id, "path": parent_session_path,
    "role": "parent", "purpose": "task_owner", "reason": "Handoff, integration, review and recovery",
    "start": None, "end": None, "cache_condition": None,
}, {
    "session_id": child_id, "path": child_session_path,
    "role": "child", "purpose": "tokenomics", "reason": "Bounded source collection",
    "start": None, "end": None, "cache_condition": None,
}]
```

Set `environment` to `local` or `cloud` on each association. Use exact session IDs and paths from this task's runtime. If finding a file is necessary, match that ID against filenames only. Never search unrelated chat contents. The collector reads only named files, consumes metadata and counters, and stores no message text, source code or credentials. Summaries and reasons must also be metadata, not copied prompts. Session paths stay in the local association log; measurement output omits them.

Local and cloud execution use the same portable Python module. In a cloud session without accessible runtime logs, associate the known runtime ID with `path=None` and `environment="cloud"`. The collector records metadata unavailability and unknown usage. Never invent a log path, scrape unrelated histories, use API billing, or substitute account-wide snapshots for task counters. If this environment exposes an explicitly associated JSONL log, collection works as it does locally. No live cloud metadata collection has been verified.

An unbounded entry selects the whole session. For a parent shared with other tasks, use an explicit UTC interval that includes preparation before spawning, subsequent review and any recovery. Its start must equal a recorded cumulative-counter timestamp. Usage is the difference after that boundary through the end. A start without an exact baseline is unknown. A fork's inherited first counter without a baseline is also unknown. Choose an end at an observed metadata boundary; a future end is incomplete. Record a final end only after the task is done. Open sessions provide provisional token observations with incomplete coverage. Never label a partial parent window full-task evidence.

Cumulative counters take precedence over last-request counters. Repeated events do not add consumption. A counter reset needs confirming last-request values; an ambiguous reset becomes unknown. Cached input is a subset of total input, never added again. Missing fields remain `None`. Effort is observed from turn metadata; cache conditions are observations or unknown, never assumptions that Sol stayed warm or Luna started cold.

```powershell
python "$env:USERPROFILE\.codex\skills\tokenomics\tokenomics_router.py" --log .tokenomics/decisions.jsonl --collect DECISION_ID
python "$env:USERPROFILE\.codex\skills\tokenomics\tokenomics_router.py" --log .tokenomics/decisions.jsonl --summary
```

Recollection replaces a decision's earlier measurement in the summary. Overlapping decision intervals make the combined rollup unknown. Report consumption by observed model, cached input and cache fraction, parent elapsed time, session seconds, accepted results, child usability, escalation and coverage. Session seconds sum concurrent sessions; parent elapsed time is wall time and must not be confused with that sum. Unknown counters make totals partial; consult coverage and per-session issues. Estimates do not enter measured totals.

Tokens are not exact subscription allowance consumption. Without an equivalent baseline, savings are unknown. Optional `record_account_snapshot(log_path, snapshot)` accepts `captured_at`, `used_percent`, `window_minutes` and `resets_at`; it labels them account-wide and potentially affected by concurrent chats or resets. Never attribute their change to a single task.

## Occasional paired comparisons

Use `record_comparison` on two already completed, explicitly associated runs. One uses Sol only; the other uses Sol plus Luna. Do not execute either arm automatically. Confirm equivalent scope and the same acceptance checks. Include parent coordination, review, required reviews and recovery in each arm.

```python
from tokenomics_router import record_comparison
record_comparison(config["log_path"], sol_only_id, sol_luna_id,
                  task_key="short-equivalence-label", acceptance_checks=["same check identifier"],
                  equivalent_tasks=True, includes_coordination_review_recovery=True)
```

The summary reports tokens by model and time per accepted result, plus effort and cache conditions for each session. Missing measurements, failed acceptance or unconfirmed equivalence prevent a valid comparison. Unequal or unknown effort/cache conditions qualify interpretation. These observations may suggest a routing benefit, but cannot establish exact subscription savings. Do not invent a baseline or treat absent savings as zero.

## Installation

The maintained project provides `install_skill.py`, a standard-library-only installer for Windows, macOS and Linux. It backs up the existing skill outside discovery folders, copies only its three managed files, and verifies hashes. For local use run `python install_skill.py`; it keeps an existing legacy `.codex/skills/tokenomics` installation when no current `.agents/skills/tokenomics` installation exists. An explicit `--target` can update this known location. For a cloud repository, run `python3 install_skill.py --repo-root /path/to/project` from the maintained project checkout; this installs under that repository's `.agents/skills/tokenomics`. Put it in environment setup, or commit the installed skill into the target repo for subsequent sessions. This requires one setup for each environment/repo; updating a local folder does not install it into your cloud account. Do not run the full `install.ps1` merely to update the skill.

In examples, use the adjacent script path from the actual skill location. The PowerShell examples show the existing Windows installation; on Linux/macOS use `python3 /actual/skill/path/tokenomics_router.py` with the same arguments.

Maintain changes in the project first. Keep one active skill folder and backups outside discoverable skill directories. Install only after the changes are concrete and reviewable, and only when authorized. Preserve unrelated global settings. New chats load updated instructions; existing chats may retain the earlier version.
