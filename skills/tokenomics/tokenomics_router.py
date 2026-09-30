"""Small, dependency-free task router for personal projects.

The router selects a configured model but deliberately does not execute it.
"""

from __future__ import annotations

import argparse
import copy
import json
import math
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping


DEFAULT_CONFIG: dict[str, Any] = {
    # Model IDs and prices live here, rather than in routing policy. Fill prices
    # from the provider bill; None means "do not claim a dollar estimate".
    "tiers": {
        "cheap": {"model": "gpt-6-luna", "max_complexity": 0.34, "input_per_million": None, "output_per_million": None},
        "standard": {"model": "gpt-6-sol", "max_complexity": 0.74, "input_per_million": None, "output_per_million": None},
        "strong": {"model": "gpt-6-astra", "max_complexity": 1.0, "input_per_million": None, "output_per_million": None},
    },
    "expected_output_tokens": {"short": 300, "normal": 900, "long": 2400},
    "low_confidence_threshold": 0.70,
    "cheap_task_types": ["format", "search", "summary", "source_collection", "mechanical_edit", "test"],
    "standard_task_types": ["architecture", "security", "hard_debugging", "integration", "planning", "design"],
    "force_strong_task_types": [],
    "high_value_task_types": [],
    "force_model": None,
    # Extra child input for its system prompt/tools, rebuilt context, and file reads.
    "handoff_context_tokens": 10000,
    "handoff_read_tokens": 500,
    # Parent input for writing the handoff and reviewing the child's result,
    # charged at the current model's rate. Tune both from logs.
    "parent_handoff_tokens": 1500,
    "log_path": None,
}


def _merge(base: Mapping[str, Any], updates: Mapping[str, Any] | None) -> dict[str, Any]:
    result = copy.deepcopy(dict(base))
    for key, value in (updates or {}).items():
        if isinstance(value, Mapping) and isinstance(result.get(key), Mapping):
            result[key] = _merge(result[key], value)
        else:
            result[key] = value
    return result


def _clamp(value: Any, default: float = 0.5) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def default_classifier(task: str, context: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """A deterministic, deliberately conservative no-network fallback."""
    words = re.findall(r"[a-z0-9]+", task.lower())

    def has(*phrase: str) -> bool:
        return any(words[i:i + len(phrase)] == list(phrase) for i in range(len(words) - len(phrase) + 1))

    if any(has(word) for word in ("architecture", "security", "migration", "integration")) or has("race", "condition") or has("root", "cause"):
        return {"task_type": "architecture", "complexity": 0.70, "expected_output_bucket": "long", "confidence": 0.80}
    if has("design"):
        return {"task_type": "design", "complexity": 0.65, "expected_output_bucket": "normal", "confidence": 0.80}
    if has("plan") or has("planning"):
        return {"task_type": "planning", "complexity": 0.65, "expected_output_bucket": "long", "confidence": 0.80}
    if has("unit", "test") or has("tests") or has("test"):
        return {"task_type": "test", "complexity": 0.25, "expected_output_bucket": "short", "confidence": 0.80}
    if (any(word in words for word in ("source", "sources"))
            and any(word in words for word in ("collect", "gather", "find", "extract", "map"))
            and not any(word in words for word in ("analyze", "assess", "decide", "interpret", "recommend", "validate"))):
        return {"task_type": "source_collection", "complexity": 0.30, "expected_output_bucket": "normal", "confidence": 0.80}
    if any(has(word) for word in ("format", "rename", "typo", "summarize")) or has("find", "files") or has("list", "files"):
        return {"task_type": "mechanical_edit", "complexity": 0.20, "expected_output_bucket": "short", "confidence": 0.80}
    return {"task_type": "unknown", "complexity": 0.50, "expected_output_bucket": "normal", "confidence": 0.0}


def _signals(task: str, context: Mapping[str, Any] | None, config: Mapping[str, Any]) -> tuple[dict[str, Any], str | None]:
    classifier: Callable[..., Mapping[str, Any]] = config.get("classifier") or default_classifier
    try:
        raw = dict(classifier(task, context))
        return {
            "task_type": str(raw.get("task_type", "unknown")),
            "complexity": _clamp(raw.get("complexity")),
            "expected_output_bucket": str(raw.get("expected_output_bucket", "normal")),
            "confidence": _clamp(raw.get("confidence"), 0.0),
        }, None
    except Exception as exc:  # Routing must remain available when an optional judge is down.
        return default_classifier(task, context), f"classifier unavailable: {type(exc).__name__}"


def estimate_tokens(text: str, model: str | None = None) -> tuple[int, str]:
    """Use the model's known tiktoken encoding, else approximate at 4 chars/token."""
    try:
        import tiktoken  # type: ignore

        encoding = tiktoken.encoding_for_model(model or "")
        return len(encoding.encode(text)), "tiktoken"
    except (ImportError, KeyError, ValueError):
        return max(1, math.ceil(len(text) / 4)), "chars/4 approximation"


def _tier_for_model(model: str, tiers: Mapping[str, Mapping[str, Any]]) -> str | None:
    return next((name for name, spec in tiers.items() if spec.get("model") == model), None)


def _next_tier(tier: str, tiers: Mapping[str, Any]) -> str:
    names = list(tiers)
    try:
        return names[min(names.index(tier) + 1, len(names) - 1)]
    except ValueError:
        return tier


def _cost(spec: Mapping[str, Any] | None, input_tokens: int, output_tokens: int) -> float | None:
    if not spec or spec.get("input_per_million") is None or spec.get("output_per_million") is None:
        return None
    return round((input_tokens * float(spec["input_per_million"]) + output_tokens * float(spec["output_per_million"])) / 1_000_000, 8)


def route_task(task: str, context: Mapping[str, Any] | None = None, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Compare staying in the current model with delegating to a child."""
    cfg = _merge(DEFAULT_CONFIG, config)
    context = dict(context or {})
    tiers = cfg["tiers"]
    signals, classifier_error = _signals(task, context, cfg)
    task_type = signals["task_type"]
    reasons: list[str] = []
    current_model = str(context.get("current_model") or cfg.get("current_model") or tiers["standard"]["model"])
    current_tier = _tier_for_model(current_model, tiers)

    forced_model = context.get("force_model") or cfg.get("force_model")
    if forced_model:
        candidate_model = str(forced_model)
        candidate_tier = _tier_for_model(candidate_model, tiers)
        reasons.append("forced model")
    else:
        if context.get("force_strong") or task_type in set(cfg["force_strong_task_types"]) | set(cfg["high_value_task_types"]):
            candidate_tier = "strong"
            reasons.append("strong task policy")
        elif context.get("force_cheap") or task_type in cfg["cheap_task_types"]:
            candidate_tier = "cheap"
            reasons.append("cheap task policy")
        elif task_type in cfg["standard_task_types"]:
            candidate_tier = "standard"
            reasons.append("standard task policy")
        elif task_type == "unknown":
            candidate_tier = "standard"
            reasons.append("unknown task type")
        else:
            candidate_tier = next((name for name, spec in tiers.items() if signals["complexity"] <= float(spec["max_complexity"])), "standard")
            if candidate_tier == "strong":
                candidate_tier = "standard"  # Astra requires an explicit policy override.
            reasons.append("complexity policy")
        # Unknown stays standard. Low confidence on a known cheap route rises to Sol.
        if task_type != "unknown" and signals["confidence"] < float(cfg["low_confidence_threshold"]):
            promoted = _next_tier(candidate_tier, tiers)
            if candidate_tier == "cheap" and promoted != candidate_tier:
                candidate_tier = promoted
                reasons.append("low classifier confidence: escalated one tier")
        candidate_model = tiers[candidate_tier]["model"]

    routing_keys = {"current_model", "force_model", "force_strong", "force_cheap", "handoff_context_tokens", "handoff_read_tokens", "parent_handoff_tokens", "input_tokens", "work_scope", "independent"}
    input_text = task + "\n" + json.dumps({k: v for k, v in context.items() if k not in routing_keys}, sort_keys=True, default=str)
    counted_tokens, token_method = estimate_tokens(input_text, current_model)
    input_tokens = int(context["input_tokens"]) if context.get("input_tokens") is not None else counted_tokens
    if context.get("input_tokens") is not None:
        token_method = "provided input_tokens"
    output_tokens = int(cfg["expected_output_tokens"].get(signals["expected_output_bucket"], cfg["expected_output_tokens"]["normal"]))
    handoff_tokens = max(0, int(context.get("handoff_context_tokens", cfg["handoff_context_tokens"]))) + max(0, int(context.get("handoff_read_tokens", cfg["handoff_read_tokens"])))

    current_spec = tiers.get(current_tier) if current_tier else None
    # The parent reads the child's output back as input, plus its own handoff/review work.
    parent_tokens = max(0, int(context.get("parent_handoff_tokens", cfg["parent_handoff_tokens"]))) + output_tokens
    parent_cost = _cost(current_spec, parent_tokens, 0)

    def estimate(model: str, spec: Mapping[str, Any] | None, extra_tokens: int) -> dict[str, Any]:
        cost = _cost(spec, input_tokens + extra_tokens, output_tokens)
        parent = parent_cost if extra_tokens else None
        if extra_tokens and cost is not None:
            cost = None if parent is None else round(cost + parent, 8)
        return {"model": model, "estimated_input_tokens": input_tokens + extra_tokens,
                "estimated_output_tokens": output_tokens, "handoff_input_tokens": extra_tokens,
                "parent_overhead_usd": parent, "estimated_cost_usd": cost}

    estimates = {"stay": estimate(current_model, current_spec, 0)}
    estimates.update({name: estimate(spec["model"], spec, handoff_tokens) for name, spec in tiers.items()})
    candidate_estimate = estimates[candidate_tier] if candidate_tier else estimate(candidate_model, None, handoff_tokens)
    if candidate_tier is None:
        estimates["forced"] = candidate_estimate
    stay_cost = estimates["stay"]["estimated_cost_usd"]
    child_cost = candidate_estimate["estimated_cost_usd"]
    explicit = bool(forced_model or context.get("force_strong") or context.get("force_cheap"))

    if candidate_model == current_model:
        action = "stay"
        reasons.append("already in selected model")
    elif explicit or (current_tier == "cheap" and candidate_tier in ("standard", "strong")):
        action = "delegate"
        reasons.append("explicit override" if explicit else "current model below required tier")
    elif stay_cost is None or child_cost is None:
        # A caller can make a qualitative delegation decision without claiming
        # dollar savings. Both signals are required so short or coupled work stays.
        cheaper_tier = current_tier in ("standard", "strong") and candidate_tier == "cheap"
        if cheaper_tier and context.get("work_scope") == "substantial" and context.get("independent") is True:
            action = "delegate"
            reasons.append("substantial independent cheap-tier work; dollar savings unverified")
        else:
            action = "stay"
            reasons.append("pricing unavailable; delegation value not established")
    elif child_cost < stay_cost:
        action = "delegate"
        reasons.append("child cost including handoff is lower")
    else:
        action = "stay"
        reasons.append("handoff does not pay")

    selected = estimates["stay"] if action == "stay" else candidate_estimate
    if selected["estimated_cost_usd"] is None:
        reasons.append("pricing unavailable; cost not estimated")
    if classifier_error:
        reasons.append(classifier_error)

    return {
        "action": action,
        "model": selected["model"],
        "tier": current_tier if action == "stay" else candidate_tier,
        "candidate_model": candidate_model,
        "candidate_tier": candidate_tier,
        "estimates": estimates,
        "task_type": task_type,
        "complexity": signals["complexity"],
        "confidence": signals["confidence"],
        "expected_output_bucket": signals["expected_output_bucket"],
        "estimated_input_tokens": selected["estimated_input_tokens"],
        "estimated_output_tokens": selected["estimated_output_tokens"],
        "estimated_cost_usd": selected["estimated_cost_usd"],
        "token_estimation_method": token_method,
        "reason": "; ".join(reasons),
        "classifier_available": classifier_error is None,
    }


def record_result(decision: Mapping[str, Any], actual_usage: Mapping[str, Any], success: bool | None = None, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Append one local JSONL record when log_path is configured; return it either way."""
    cfg = _merge(DEFAULT_CONFIG, config)
    record = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "action": decision.get("action"), "model": decision.get("model"), "tier": decision.get("tier"), "task_type": decision.get("task_type"),
        "candidate_tier": decision.get("candidate_tier"),
        "complexity": decision.get("complexity"), "confidence": decision.get("confidence"),
        "estimated_input_tokens": decision.get("estimated_input_tokens"), "estimated_output_tokens": decision.get("estimated_output_tokens"),
        "estimated_cost_usd": decision.get("estimated_cost_usd"), "success": success,
        **dict(actual_usage),
    }
    path = cfg.get("log_path")
    if path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True, default=str) + "\n")
    return record


def summarize_usage(log_path: str | Path) -> dict[str, Any]:
    """Summarize locally logged results; feedback fields are optional."""
    rows = [json.loads(line) for line in Path(log_path).read_text(encoding="utf-8").splitlines() if line.strip()]
    if not rows:
        return {"records": 0}
    cost_pairs = [(r["estimated_cost_usd"], r["actual_cost_usd"]) for r in rows if r.get("estimated_cost_usd") is not None and r.get("actual_cost_usd") is not None]
    cheap = [r for r in rows if r.get("tier") == "cheap" and r.get("success") is not None]
    expected = {"cheap": 0, "standard": 1, "strong": 2}
    feedback = [r for r in rows if r.get("should_have_tier") in expected and r.get("tier") in expected]
    relative_error = round(sum(abs(a - b) / max(b, 0.000001) for a, b in cost_pairs) / len(cost_pairs), 4) if cost_pairs else None
    return {
        "records": len(rows),
        "cost_mean_absolute_relative_error": relative_error,
        "cheap_model_success_rate": (round(sum(bool(r["success"]) for r in cheap) / len(cheap), 4) if cheap else None),
        "escalation_frequency": round(sum(bool(r.get("retry") or r.get("escalated_from")) for r in rows) / len(rows), 4),
        "over_routed": sum(expected[r["tier"]] > expected[r["should_have_tier"]] for r in feedback),
        "under_routed": sum(expected[r["tier"]] < expected[r["should_have_tier"]] for r in feedback),
        "estimated_savings_usd": round(sum(float(r.get("baseline_cost_usd", 0)) - float(r.get("actual_cost_usd", 0)) for r in rows if r.get("baseline_cost_usd") is not None and r.get("actual_cost_usd") is not None), 8),
        "models": dict(Counter(r.get("model") for r in rows)),
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Recommend a model route without executing it")
    parser.add_argument("task", nargs="?", help="Task summary; reads stdin when omitted")
    parser.add_argument("--current-model", required=True)
    parser.add_argument("--work-scope", choices=("small", "substantial"), default="small")
    parser.add_argument("--independent", action="store_true")
    parser.add_argument("--input-tokens", type=int)
    parser.add_argument("--config", type=Path, help="Optional JSON configuration with models and prices")
    args = parser.parse_args()
    task = args.task if args.task is not None else sys.stdin.read().strip()
    if not task:
        parser.error("provide a task or pipe one on stdin")
    config = json.loads(args.config.read_text(encoding="utf-8")) if args.config else None
    context = {"current_model": args.current_model, "work_scope": args.work_scope,
               "independent": args.independent}
    if args.input_tokens is not None:
        context["input_tokens"] = args.input_tokens
    print(json.dumps(route_task(task, context=context, config=config), indent=2))
