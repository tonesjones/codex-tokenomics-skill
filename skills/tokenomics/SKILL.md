---
name: tokenomics
description: Recommend and verify cost-aware model routing. Includes a small portable router that chooses configured cheap, standard, or strong tiers, estimates cost, and can log actual usage.
---

# Tokenomics

Apply the global model-routing policy in `~/.codex/AGENTS.md` when working in Codex. For another project, use `tokenomics_router.py` directly: it returns a model decision; the calling project owns the actual model call.

**Routing is the capability. Jev is an implementation dependency, not the public interface.**

## When to route

At the first planning checkpoint, compare likely savings with switching and child handoff overhead. Do small or tightly coupled tasks directly in the current model. A child must rebuild context and may reread files, so count those input tokens before recommending delegation.

The router keeps the existing smallest-capable policy but makes its model IDs and prices project configuration instead of policy literals:

- `cheap`: clear, bounded work such as searching, summaries, formatting, mechanical edits, tests, and narrow refactors.
- `standard`: architecture, security-sensitive work, hard debugging, integration, planning, and the fallback for unknown task types.
- `strong`: an exception for explicitly forced strong work or project-configured high-value/strong task types; use it only for the hardest work when Sol is genuinely insufficient.

Try Luna on sufficiently large bounded work when the handoff still pays. Escalate a failed Luna attempt to Sol once with the useful evidence; avoid repeated retries. Escalate Sol to Astra only for exceptional difficulty, not as a routine third pass.

## Codex compatibility

At the first meaningful planning checkpoint, recommend a manual top-level switch when the active model is clearly mismatched for nontrivial work. Do not block progress or repeat it without a material scope change. For child work, use a self-contained prompt or small context fork when an explicit override is available; runtime metadata, not an accepted request, is evidence of the model that ran. Poteto Mode can still read `~/.agents/pstack-models.md` for role defaults.

## Portable API

Copy `tokenomics_router.py` into a project (or import it from this installed skill). It has no required package dependencies.

```python
from tokenomics_router import route_task, record_result

config = {
    "tiers": {
        "cheap": {"model": "my-small-model", "max_complexity": 0.34,
                  "input_per_million": 0.50, "output_per_million": 2.00},
        "standard": {"model": "my-default-model", "max_complexity": 0.74,
                     "input_per_million": 2.00, "output_per_million": 8.00},
        "strong": {"model": "my-best-model", "max_complexity": 1.0,
                   "input_per_million": 10.00, "output_per_million": 30.00},
    },
    "log_path": ".tokenomics/usage.jsonl",
}

decision = route_task("Summarize these test failures", config=config)
# If decision["action"] == "stay", do the work in the current model.
# If decision["action"] == "delegate", call a child with decision["model"].
record_result(decision, {"actual_input_tokens": 1200, "actual_output_tokens": 350,
                         "actual_cost_usd": 0.0013}, success=True, config=config)
```

`route_task(task, context=None, config=None)` returns `action` (`stay` or `delegate`), the selected `model` and `tier`, an advisory `candidate_model`/`candidate_tier`, a concise `reason`, and `estimates` for staying and for each child tier. Each estimate shows input/output tokens, extra handoff input tokens, and dollar cost or `None`. The existing top-level token/cost fields describe the selected action. `record_result(decision, actual_usage, success=None)` appends local JSONL only when `log_path` is set. `summarize_usage(path)` reports mean absolute relative cost error, cheap-tier success, escalation frequency, over/under-routing where feedback exists, and observed savings where a baseline is recorded.

## Signals, policy, and fallbacks

The normal flow is:

`task → optional classifier signals → local tier policy → compare stay and child costs including handoff → calling project executes → optional actual-usage record`

A classifier returns only `task_type`, `complexity` (0..1), `expected_output_bucket` (`short`, `normal`, `long`), and `confidence` (0..1). Configure any local callable as `config["classifier"]`; projects never need to import or know about Jev.

If the classifier is absent, Tokenomics uses whole-word rules as a conservative deterministic fallback. If it fails, routing still works. Unknown task types use standard. Low confidence on a known cheap task rises one tier to standard; normal uncertainty does not automatically invoke Astra. `context={"force_model": "..."}`, `force_strong`, and `force_cheap` override ordinary selection. `force_model`, task lists, thresholds, output buckets, tiers, prices, and log path are configurable.

Pass the observed active model as `context["current_model"]`; otherwise the router assumes the configured standard model. Pass `context["input_tokens"]` if the caller knows the real prompt size. Handoff adds configurable `handoff_context_tokens` (default 1000) and `handoff_read_tokens` (default 500) to every child estimate; override them in config or context based on actual project logs. Delegate to a cheaper tier only when its estimated dollar cost including handoff is lower. If either price is unknown, stay unless the caller explicitly forces a model/tier or the current model is below the required tier. No price is invented.

An unknown forced model or missing price produces `estimated_cost_usd: None` and says so in `reason`; Tokenomics never fabricates a dollar amount.

## Jev's role

Jev is suitable as an optional classifier: its public material describes typed `Choice`, `Score`, and yes/no (`Noul`) questions over shared text/JSON state, with scores/probabilities/confidence and model-routing as a use case. It is not the model being routed to and must not calculate dollars. Keep its request/API-key handling in a project-specific `classifier` callable, then return the four signals above. This keeps secrets out of the skill, avoids an HTTP dependency, and permits easy replacement.

Validate the live Jev endpoint, authentication header, question schema, and calibration on your own representative tasks before enabling it. If no Jev key is configured or its request fails, use the built-in fallback; routing remains local and deterministic.

## Cost estimation and actual use

If `tiktoken` knows the current model, the router uses its encoding for input counting. Otherwise it uses a documented `ceil(characters / 4)` approximation; it never substitutes a different model's encoding as if exact. Output token estimates come from configurable buckets. Costs are arithmetic from the configured per-million input/output rates. Unknown model or pricing yields `None`.

After execution, record provider-reported `actual_input_tokens`, `actual_output_tokens`, and `actual_cost_usd` when available. Optional `retry`, `escalated_from`, `baseline_cost_usd`, and `should_have_tier` fields make the small summary more useful. JSONL is intentionally local and human-readable.

## Portability steps

1. Copy `tokenomics_router.py` into the calling project.
2. Set its available models and current provider prices in one config object.
3. Call `route_task`, honor `action`, execute in the current model or delegate through your existing client, then optionally call `record_result`.
4. Start with the default classifier; add a Jev-backed callable only after checking its decisions against real tasks.
5. Periodically run `summarize_usage` and adjust thresholds/lists from outcomes, not guesses.

## Deliberate omissions

No database, service, dashboard, paid API, provider client, automatic execution, elaborate DSL, or training loop is included. Top-level Codex model switches remain advisory; explicit child-model overrides are attempts until runtime metadata confirms what actually ran.
