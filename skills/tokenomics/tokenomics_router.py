"""Small, dependency-free task router for personal projects.

The router selects a configured model but deliberately does not execute it.
"""

from __future__ import annotations

import copy
import json
import math
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
    "cheap_task_types": ["format", "search", "summary", "mechanical_edit", "test"],
    "force_strong_task_types": ["architecture", "security", "hard_debugging", "integration"],
    "high_value_task_types": [],
    "force_model": None,
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
    text = task.lower()
    if any(word in text for word in ("format", "rename", "typo", "summarize", "find files", "list files")):
        return {"task_type": "mechanical_edit", "complexity": 0.20, "expected_output_bucket": "short", "confidence": 0.80}
    if any(word in text for word in ("architecture", "security", "race condition", "migration", "root cause", "design")):
        return {"task_type": "architecture", "complexity": 0.80, "expected_output_bucket": "long", "confidence": 0.72}
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
    """Use tiktoken when already installed; otherwise use the documented 4 chars/token estimate."""
    try:
        import tiktoken  # type: ignore

        encoding = tiktoken.encoding_for_model(model or "gpt-4o")
        return len(encoding.encode(text)), "tiktoken"
    except Exception:
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
    """Return a route and estimate. The calling project owns model execution."""
    cfg = _merge(DEFAULT_CONFIG, config)
    context = dict(context or {})
    tiers = cfg["tiers"]
    signals, classifier_error = _signals(task, context, cfg)
    task_type = signals["task_type"]
    reasons: list[str] = []

    forced_model = context.get("force_model") or cfg.get("force_model")
    if forced_model:
        model = str(forced_model)
        tier = _tier_for_model(model, tiers)
        reasons.append("forced model")
    else:
        if context.get("force_strong") or task_type in set(cfg["force_strong_task_types"]) | set(cfg["high_value_task_types"]):
            tier = "strong"
            reasons.append("strong task policy")
        elif context.get("force_cheap") or task_type in cfg["cheap_task_types"]:
            tier = "cheap"
            reasons.append("cheap task policy")
        elif task_type == "unknown":
            tier = "standard"
            reasons.append("unknown task type")
        else:
            tier = next((name for name, spec in tiers.items() if signals["complexity"] <= float(spec["max_complexity"])), list(tiers)[-1])
            reasons.append("complexity policy")
        # "unknown" deliberately stays standard: it is the documented safe
        # default, not a low-confidence claim about a known category.
        if task_type != "unknown" and signals["confidence"] < float(cfg["low_confidence_threshold"]):
            promoted = _next_tier(tier, tiers)
            if promoted != tier:
                tier = promoted
                reasons.append("low classifier confidence: escalated one tier")
        model = tiers[tier]["model"]

    spec = tiers.get(tier) if tier else None
    input_text = task + "\n" + json.dumps(context, sort_keys=True, default=str)
    input_tokens, token_method = estimate_tokens(input_text, model)
    output_tokens = int(cfg["expected_output_tokens"].get(signals["expected_output_bucket"], cfg["expected_output_tokens"]["normal"]))
    estimated_cost = _cost(spec, input_tokens, output_tokens)
    if estimated_cost is None:
        reasons.append("pricing unavailable; cost not estimated")
    if classifier_error:
        reasons.append(classifier_error)

    return {
        "model": model,
        "tier": tier,
        "task_type": task_type,
        "complexity": signals["complexity"],
        "confidence": signals["confidence"],
        "expected_output_bucket": signals["expected_output_bucket"],
        "estimated_input_tokens": input_tokens,
        "estimated_output_tokens": output_tokens,
        "estimated_cost_usd": estimated_cost,
        "token_estimation_method": token_method,
        "reason": "; ".join(reasons),
        "classifier_available": classifier_error is None,
    }


def record_result(decision: Mapping[str, Any], actual_usage: Mapping[str, Any], success: bool | None = None, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Append one local JSONL record when log_path is configured; return it either way."""
    cfg = _merge(DEFAULT_CONFIG, config)
    record = {
        "recorded_at": datetime.now(timezone.utc).isoformat(),
        "model": decision.get("model"), "tier": decision.get("tier"), "task_type": decision.get("task_type"),
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
    return {
        "records": len(rows),
        "estimate_accuracy": (round(sum(abs(a - b) / max(b, 0.000001) for a, b in cost_pairs) / len(cost_pairs), 4) if cost_pairs else None),
        "cheap_model_success_rate": (round(sum(bool(r["success"]) for r in cheap) / len(cheap), 4) if cheap else None),
        "escalation_frequency": round(sum(bool(r.get("retry") or r.get("escalated_from")) for r in rows) / len(rows), 4),
        "over_routed": sum(expected[r["tier"]] > expected[r["should_have_tier"]] for r in feedback),
        "under_routed": sum(expected[r["tier"]] < expected[r["should_have_tier"]] for r in feedback),
        "estimated_savings_usd": round(sum(float(r.get("baseline_cost_usd", 0)) - float(r.get("actual_cost_usd", 0)) for r in rows if r.get("baseline_cost_usd") is not None and r.get("actual_cost_usd") is not None), 8),
        "models": dict(Counter(r.get("model") for r in rows)),
    }
