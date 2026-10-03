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
from uuid import uuid4
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Mapping


DEFAULT_CONFIG: dict[str, Any] = {
    # Routing is qualitative. Tokens do not map to subscription allowance.
    "tiers": {
        "cheap": {"model": "gpt-6-luna", "max_complexity": 0.34},
        "standard": {"model": "gpt-6.1-sol", "max_complexity": 0.74},
        "strong": {"model": "gpt-6-astra", "max_complexity": 1.0},
    },
    "model_aliases": {"gpt-6-sol": "standard"},
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
    # Estimate separately from measured counters. Tune from selected audits.
    "parent_handoff_tokens": 1500,
    # Additional parent input still needed after handoff; this is separate from
    # the child's rebuilt context and defaults to none when unknown.
    "parent_remaining_input_tokens": 0,
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
    if any(word in words for word in ("analyze", "assess", "decide", "interpret", "recommend", "validate", "authentication", "authorization")):
        return {"task_type": "integration", "complexity": 0.70, "expected_output_bucket": "normal", "confidence": 0.80}
    if has("unit", "test") or has("tests") or has("test"):
        return {"task_type": "test", "complexity": 0.25, "expected_output_bucket": "short", "confidence": 0.80}
    if (any(word in words for word in ("source", "sources"))
            and any(word in words for word in ("collect", "gather", "find", "extract", "map", "research"))
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


def route_task(task: str, context: Mapping[str, Any] | None = None, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Compare staying in the current model with delegating to a child."""
    cfg = _merge(DEFAULT_CONFIG, config)
    context = dict(context or {})
    tiers = cfg["tiers"]
    assessment = context.get("assessment")
    if assessment is not None:
        cfg["classifier"] = lambda task, context: assessment
    signals, classifier_error = _signals(task, context, cfg)
    task_type = signals["task_type"]
    reasons: list[str] = []
    current_model = str(context.get("current_model") or cfg.get("current_model") or "unknown")
    current_tier = _tier_for_model(current_model, tiers) or cfg.get("model_aliases", {}).get(current_model)
    if current_tier not in tiers:
        current_tier = None

    forced_model = context.get("force_model") or cfg.get("force_model")
    if forced_model:
        candidate_model = str(forced_model)
        candidate_tier = _tier_for_model(candidate_model, tiers)
        reasons.append("forced model")
    else:
        if context.get("force_strong") or task_type in set(cfg["force_strong_task_types"]) | set(cfg["high_value_task_types"]):
            candidate_tier = "strong"
            reasons.append("strong task policy")
        elif (context.get("force_cheap") or task_type in cfg["cheap_task_types"]) and signals["complexity"] <= float(tiers["cheap"]["max_complexity"]):
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
            if promoted == "strong" and not (context.get("force_strong") or task_type in set(cfg["force_strong_task_types"]) | set(cfg["high_value_task_types"])):
                promoted = candidate_tier
            if candidate_tier == "cheap" and promoted != candidate_tier:
                candidate_tier = promoted
                reasons.append("low classifier confidence: escalated one tier")
        candidate_model = tiers[candidate_tier]["model"]

    routing_keys = {"current_model", "force_model", "force_strong", "force_cheap", "approval_granted", "handoff_context_tokens", "handoff_read_tokens", "parent_handoff_tokens", "parent_remaining_input_tokens", "input_tokens", "child_input_tokens", "stay_cached_input_tokens", "child_cached_input_tokens", "work_scope", "independent", "assessment"}
    input_text = task + "\n" + json.dumps({k: v for k, v in context.items() if k not in routing_keys}, sort_keys=True, default=str)
    counted_tokens, token_method = estimate_tokens(input_text, current_model)
    input_tokens = int(context["input_tokens"]) if context.get("input_tokens") is not None else counted_tokens
    if context.get("input_tokens") is not None:
        token_method = "provided input_tokens"
    child_input_tokens = max(0, int(context.get("child_input_tokens", input_tokens)))
    stay_cached_tokens = max(0, int(context.get("stay_cached_input_tokens", 0)))
    child_cached_tokens = max(0, int(context.get("child_cached_input_tokens", 0)))
    output_tokens = int(cfg["expected_output_tokens"].get(signals["expected_output_bucket"], cfg["expected_output_tokens"]["normal"]))
    handoff_tokens = max(0, int(context.get("handoff_context_tokens", cfg["handoff_context_tokens"]))) + max(0, int(context.get("handoff_read_tokens", cfg["handoff_read_tokens"])))

    def estimate(model, extra_tokens, base_input=input_tokens, cached_tokens=stay_cached_tokens, include_parent=True):
        return {"model": model, "estimated_input_tokens": base_input + extra_tokens,
                "estimated_output_tokens": output_tokens,
                "estimated_cached_input_tokens": min(base_input, cached_tokens),
                "estimated_parent_input_tokens": (max(0, int(context.get("parent_remaining_input_tokens", cfg["parent_remaining_input_tokens"])))
                                                  + cfg["parent_handoff_tokens"] + output_tokens) if include_parent else 0}

    estimates = {"stay": estimate(current_model, 0, include_parent=False)}
    estimates.update({name: estimate(spec["model"], handoff_tokens, child_input_tokens, child_cached_tokens)
                      for name, spec in tiers.items()})
    candidate_estimate = estimates.get(candidate_tier) or estimate(candidate_model, handoff_tokens, child_input_tokens)
    explicit = bool(forced_model or context.get("force_strong") or context.get("force_cheap")
                    or task_type in set(cfg["force_strong_task_types"]) | set(cfg["high_value_task_types"]))

    approval_required = (candidate_tier == "strong" and candidate_model != current_model
                         and context.get("approval_granted") is not True)
    if approval_required:
        action = "request_approval"
        reasons.append("Astra requires explicit approval")
    elif candidate_model == current_model:
        action = "stay"
        reasons.append("already in selected model")
    elif explicit or (current_tier == "cheap" and candidate_tier in ("standard", "strong")):
        action = "delegate"
        reasons.append("explicit override" if explicit else "current model below required tier")
    elif current_tier in ("standard", "strong") and candidate_tier == "cheap" and context.get("work_scope") == "substantial" and context.get("independent") is True:
        action = "delegate"
        reasons.append("substantial independent bounded work; subscription savings unknown")
    else:
        action = "stay"
        reasons.append("small, coupled, or unsuitable work: keep execution local")

    selected = estimates["stay"] if action in ("stay", "request_approval") else candidate_estimate
    if classifier_error:
        reasons.append(classifier_error)

    status = "ready" if current_tier is not None else "needs_model_identity"
    if status != "ready":
        action = "stay"
        selected = estimates["stay"]
        reasons = ["current model identity or tier unresolved; resolve before routing"]
        approval_required = False

    return {
        "status": status,
        "current_model": current_model,
        "decision_id": str(uuid4()),
        "deliverable": context.get("deliverable", task),
        "action": action,
        "model": selected["model"],
        "tier": current_tier if action in ("stay", "request_approval") else candidate_tier,
        "candidate_model": candidate_model,
        "candidate_tier": candidate_tier,
        "approval_required": approval_required,
        "estimates": estimates,
        "task_type": task_type,
        "complexity": signals["complexity"],
        "confidence": signals["confidence"],
        "expected_output_bucket": signals["expected_output_bucket"],
        "estimated_input_tokens": selected["estimated_input_tokens"],
        "estimated_output_tokens": selected["estimated_output_tokens"],
        "token_estimation_method": token_method,
        "reason": "; ".join(reasons),
        "classifier_available": classifier_error is None,
    }


# All persisted fields are metadata. Unknown runtime values are represented by None.
TOKEN_FIELDS = ("input_tokens", "cached_input_tokens", "output_tokens")
DECISION_FIELDS = ("decision_id", "status", "action", "model", "current_model", "tier",
                   "candidate_model", "candidate_tier", "task_type", "deliverable",
                   "complexity", "confidence", "reason")


def _rows(path):
    target = Path(path)
    return [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines() if line.strip()] if target.exists() else []


def _append(record, config):
    path = (config or {}).get("log_path")
    if path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    return record


def record_result(decision: Mapping[str, Any], actual_usage: Mapping[str, Any],
                  success: bool | None = None, config: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Keep decision identity immutable; success is the legacy full-task acceptance argument."""
    stage = actual_usage.get("stage", "outcome")
    if stage not in ("checkpoint", "outcome"):
        raise ValueError("stage must be checkpoint or outcome")
    decision_id = decision.get("decision_id")
    if not decision_id:
        raise ValueError("use the decision returned by route_task, including its decision_id")
    original = decision
    if (config or {}).get("log_path"):
        checkpoints = [r for r in _rows(config["log_path"]) if r.get("decision_id") == decision_id and r.get("stage") == "checkpoint"]
        if checkpoints:
            original = checkpoints[0]
        elif stage == "outcome":
            raise ValueError("record a checkpoint before its outcome")
    record = {k: original.get(k) for k in DECISION_FIELDS}
    record.update(schema_version=1, stage=stage, recorded_at=datetime.now(timezone.utc).isoformat())
    if stage == "checkpoint":
        record["retrospective"] = original.get("retrospective", bool(actual_usage.get("retrospective", False)))
        record["estimates"] = {"input_tokens": decision.get("estimated_input_tokens"),
                               "output_tokens": decision.get("estimated_output_tokens"),
                               "method": decision.get("token_estimation_method")}
    else:
        record.update(task_accepted=actual_usage.get("task_accepted", success),
                      child_output_usable=actual_usage.get("child_output_usable"),
                      escalated=actual_usage.get("escalated"),
                      requested_child_model=actual_usage.get("requested_child_model"),
                      observed_child_model=actual_usage.get("observed_child_model"),
                      retries=actual_usage.get("retries"), recovery=actual_usage.get("recovery"))
        if record["retries"] is not None and (not isinstance(record["retries"], int) or isinstance(record["retries"], bool) or record["retries"] < 0):
            raise ValueError("retries must be a nonnegative count or None")
        if record["recovery"] is not None and not isinstance(record["recovery"], bool):
            raise ValueError("recovery must be a boolean or None")
        for key in ("task_accepted", "child_output_usable", "escalated"):
            if record[key] is not None and not isinstance(record[key], bool):
                raise ValueError(f"{key} must be a boolean or None")
    return _append(record, config)


def associate_sessions(decision, sessions, config=None, *, all_children_accounted=None):
    """Explicit allowlist only. Parent bounds must include preparation, review and recovery."""
    clean = []
    seen = set()
    for session in sessions:
        item = {k: session.get(k) for k in ("session_id", "path", "role", "purpose", "reason", "start", "end", "cache_condition", "environment")}
        if not item["session_id"] or item["session_id"] in seen:
            raise ValueError("each session needs a unique runtime ID")
        item["environment"] = item["environment"] or "local"
        if item["environment"] not in ("local", "cloud", "unknown"):
            raise ValueError("environment must be local, cloud or unknown")
        if item["role"] not in ("parent", "child"):
            raise ValueError("role must be parent or child")
        if item["purpose"] not in ("task_owner", "tokenomics", "required_review", "other") or not item["reason"]:
            raise ValueError("provide the delegation purpose and a short metadata reason")
        for key in ("start", "end"):
            if item[key]:
                _time(item[key])
        if item["start"] and item["end"] and _time(item["start"]) >= _time(item["end"]):
            raise ValueError("session start must precede end")
        seen.add(item["session_id"])
        clean.append(item)
    if sum(s["role"] == "parent" for s in clean) != 1:
        raise ValueError("associate exactly one parent and every related child")
    return _append({"stage": "association", "association_id": str(uuid4()), "decision_id": decision["decision_id"],
                    "sessions": clean, "all_children_accounted": all_children_accounted}, config)


def _time(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timestamps need a timezone")
    return result


def collect_session(session):
    """Read only metadata/counters from one named file, never retain message contents.

    Cumulative totals are authoritative; last_token_usage is never added to them.
    A decreasing counter starts a new segment only if last usage confirms the reset.
    Otherwise the ambiguous fields become unknown instead of reporting a guessed sum.
    """
    result = {k: session.get(k) for k in ("session_id", "role", "purpose", "reason", "start", "end", "cache_condition", "environment")}
    result.update(models={}, efforts=[], elapsed_seconds=None, retries=None, recovery=None,
                  counter_events=0, counter_resets=0, issues=[], complete=False)
    if not session.get("path"):
        result["issues"].append("session metadata unavailable; usage unknown")
        return result
    start = _time(session["start"]) if session.get("start") else None
    end = _time(session["end"]) if session.get("end") else None
    previous = None
    model = None
    identity = None
    forked = False
    first_time = last_time = previous_time = None
    effort = None
    finished = False
    seen = set()
    runtime_events = set()
    bad = set()
    try:
        handle = Path(session["path"]).open(encoding="utf-8")
    except OSError:
        result["issues"].append("session unavailable")
        return result
    with handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                result["issues"].append("malformed event")
                bad.update(TOKEN_FIELDS)
                continue
            kind, payload = row.get("type"), row.get("payload", {})
            if kind not in ("session_meta", "turn_context", "event_msg"):
                continue
            if kind == "session_meta":
                identity = payload.get("id")
                forked = bool(payload.get("forked_from_id") or payload.get("forked_from"))
                continue
            timestamp = row.get("timestamp")
            if not timestamp:
                continue
            try:
                stamp = _time(timestamp)
            except ValueError:
                bad.update(TOKEN_FIELDS)
                result["issues"].append("invalid event timestamp")
                continue
            if end and stamp > end:
                continue
            inside = not start or stamp > start
            if kind == "turn_context":
                model = payload.get("model")
                effort = {"model": model, "effort": payload.get("effort", payload.get("reasoning_effort"))}
            if inside:
                first_time = first_time or stamp
                last_time = stamp
            if kind != "event_msg":
                continue
            event = payload.get("type")
            if inside and event in ("retry", "recovery_started"):
                marker = (event, payload.get("event_id") or timestamp)
                if marker not in runtime_events:
                    runtime_events.add(marker)
                    if event == "retry":
                        result["retries"] = (result["retries"] or 0) + 1
                    else:
                        result["recovery"] = True
            if inside and event == "task_started":
                finished = False
            if inside and event in ("task_complete", "task_completed"):
                finished = True
            if event != "token_count":
                continue
            info = payload.get("info") or {}
            total = info.get("total_token_usage")
            if not total:
                if inside:
                    bad.update(TOKEN_FIELDS)
                    result["issues"].append("cumulative counters missing")
                continue
            signature = (timestamp, json.dumps(total, sort_keys=True))
            if signature in seen:
                continue
            seen.add(signature)
            values = {k: total.get(k) for k in TOKEN_FIELDS}
            if any(v is not None and (not isinstance(v, int) or isinstance(v, bool) or v < 0) for v in values.values()):
                bad.update(TOKEN_FIELDS)
                result["issues"].append("invalid counter")
                continue
            if not inside:
                previous = values
                previous_time = stamp
                continue
            if effort is not None and effort not in result["efforts"]:
                result["efforts"].append(effort)
            if start and (previous_time is None or previous_time < start):
                bad.update(TOKEN_FIELDS)
                result["issues"].append("start is not a cumulative counter boundary")
            result["counter_events"] += 1
            bucket = result["models"].setdefault(model or "unknown", dict.fromkeys(TOKEN_FIELDS, 0))
            reset = previous and any(values[k] is not None and previous[k] is not None and values[k] < previous[k] for k in TOKEN_FIELDS)
            last = info.get("last_token_usage") or {}
            if reset:
                result["counter_resets"] += 1
            for key in TOKEN_FIELDS:
                current = values[key]
                prior = previous.get(key) if previous else 0
                if current is None or prior is None:
                    bad.add(key)
                    continue
                if previous is None and (start or forked):
                    bad.add(key)
                    continue
                if reset:
                    if all(values[k] is not None and values[k] == last.get(k) for k in TOKEN_FIELDS):
                        delta = current
                    else:
                        bad.add(key)
                        continue
                else:
                    delta = current - prior
                bucket[key] += delta
            previous = values
            previous_time = stamp
            if values["cached_input_tokens"] is not None and values["input_tokens"] is not None and values["cached_input_tokens"] > values["input_tokens"]:
                bad.add("cached_input_tokens")
    for bucket in result["models"].values():
        if bucket["cached_input_tokens"] > bucket["input_tokens"]:
            bad.add("cached_input_tokens")
    if identity != session["session_id"]:
        result["models"] = {}
        result["issues"].append("session identity mismatch")
        return result
    if not result["counter_events"]:
        result["issues"].append("no counters in selected interval")
    if bad:
        result["issues"].append("missing or ambiguous counter fields: " + ", ".join(sorted(bad)))
        for bucket in result["models"].values():
            for key in bad:
                bucket[key] = None
    if end and (last_time is None or last_time < end):
        result["issues"].append("end is beyond observed metadata")
    if first_time and last_time and (not end and finished or end and last_time >= end):
        result["elapsed_seconds"] = max(0, ((end or last_time) - (start or first_time)).total_seconds())
    result["observed_start"] = first_time.isoformat() if first_time else None
    result["observed_end"] = last_time.isoformat() if last_time else None
    result["complete"] = bool(result["models"]) and not bad and "unknown" not in result["models"] and not result["issues"] and bool(end or finished)
    if not end and not finished:
        result["issues"].append("session interval still open")
    return result


def aggregate_sessions(sessions, all_children_accounted=None):
    models = {}
    for session in sessions:
        for model, tokens in session["models"].items():
            target = models.setdefault(model, dict.fromkeys(TOKEN_FIELDS, 0))
            for key in TOKEN_FIELDS:
                target[key] = None if target[key] is None or tokens[key] is None else target[key] + tokens[key]
    parent = next((s for s in sessions if s["role"] == "parent"), {})
    child_bounds_fit = all(s["role"] == "parent" or (
        (parent.get("start") or parent.get("observed_start")) and (parent.get("end") or parent.get("observed_end")) and
        (s.get("start") or s.get("observed_start")) and (s.get("end") or s.get("observed_end")) and
        _time(s.get("start") or s["observed_start"]) >= _time(parent.get("start") or parent["observed_start"]) and
        _time(s.get("end") or s["observed_end"]) <= _time(parent.get("end") or parent["observed_end"])) for s in sessions)
    return {"sessions": sessions, "models": models, "child_bounds_fit_parent": child_bounds_fit,
            "elapsed_seconds": parent.get("elapsed_seconds"),
            "session_seconds": sum(s["elapsed_seconds"] for s in sessions) if all(s["elapsed_seconds"] is not None for s in sessions) else None,
            "complete": child_bounds_fit and all_children_accounted is True and bool(sessions) and all(s["complete"] for s in sessions),
            "all_children_accounted": all_children_accounted}


def collect_usage(log_path, decision_id):
    """Recompute a decision's latest explicit association, replacing prior audit in summaries."""
    rows = _rows(log_path)
    if not any(r.get("stage") == "checkpoint" and r.get("decision_id") == decision_id for r in rows):
        raise ValueError("unknown decision ID")
    associations = [r for r in rows if r.get("stage") == "association" and r.get("decision_id") == decision_id]
    if not associations:
        measurement = aggregate_sessions([])
    else:
        association = associations[-1]
        measurement = aggregate_sessions([collect_session(s) for s in association["sessions"]], association["all_children_accounted"])
    return _append({"stage": "measurement", "decision_id": decision_id,
                    "association_id": associations[-1]["association_id"] if associations else None,
                    "recorded_at": datetime.now(timezone.utc).isoformat(), **measurement}, {"log_path": log_path})


def record_comparison(log_path, sol_only_id, sol_luna_id, *, task_key, acceptance_checks,
                      equivalent_tasks, includes_coordination_review_recovery):
    """Record an occasional human-selected pair. Never executes or duplicates tasks."""
    rows = _rows(log_path)
    decisions = {r.get("decision_id"): r for r in rows if r.get("stage") == "checkpoint"}
    if sol_only_id == sol_luna_id or any(i not in decisions for i in (sol_only_id, sol_luna_id)):
        raise ValueError("comparison needs two different recorded decisions")
    if not task_key or not acceptance_checks:
        raise ValueError("provide an equivalence key and the same acceptance checks for both tasks")
    return _append({"stage": "comparison", "comparison_id": str(uuid4()), "sol_only_id": sol_only_id,
                    "sol_luna_id": sol_luna_id, "task_key": task_key,
                    "acceptance_checks": list(acceptance_checks), "equivalent_tasks": equivalent_tasks,
                    "includes_coordination_review_recovery": includes_coordination_review_recovery}, {"log_path": log_path})


def record_account_snapshot(log_path, snapshot):
    """Optional account-wide context, never attributed to a task or converted to savings."""
    return _append({"stage": "account_snapshot", "scope": "account-wide",
                    "caveat": "Concurrent chats and resets can affect these values; attribution unknown.",
                    **{k: snapshot.get(k) for k in ("captured_at", "used_percent", "window_minutes", "resets_at")}}, {"log_path": log_path})


def summarize_usage(log_path: str | Path) -> dict[str, Any]:
    rows = _rows(log_path)
    decisions = {r["decision_id"]: r for r in rows if r.get("stage") == "checkpoint" and r.get("decision_id")}
    outcomes = {r["decision_id"]: r for r in rows if r.get("stage") == "outcome" and r.get("decision_id") in decisions}
    associations = {r["decision_id"]: r for r in rows if r.get("stage") == "association"}
    measurements = {r["decision_id"]: r for r in rows if r.get("stage") == "measurement" and r.get("decision_id") in decisions}
    measurements = {identity: m for identity, m in measurements.items() if m.get("association_id") == associations.get(identity, {}).get("association_id")}
    models = {}
    for measurement in measurements.values():
        for model, tokens in measurement["models"].items():
            bucket = models.setdefault(model, {"measured_input_tokens": 0, "measured_cached_input_tokens": 0, "measured_output_tokens": 0,
                                               "unknown_fields": 0})
            for key in TOKEN_FIELDS:
                if tokens[key] is None:
                    bucket["unknown_fields"] += 1
                else:
                    bucket["measured_" + key] += tokens[key]
    # Reusing a session across overlapping decision intervals makes the rollup ambiguous.
    intervals = {}
    overlap = False
    for measurement in measurements.values():
        for s in measurement["sessions"]:
            for prior in intervals.get(s["session_id"], []):
                if not (s.get("end") and prior.get("start") and _time(s["end"]) <= _time(prior["start"]) or
                        prior.get("end") and s.get("start") and _time(prior["end"]) <= _time(s["start"])):
                    overlap = True
            intervals.setdefault(s["session_id"], []).append(s)
    for bucket in models.values():
        bucket["cache_fraction"] = (bucket["measured_cached_input_tokens"] / bucket["measured_input_tokens"]
                                    if bucket["measured_input_tokens"] and not bucket["unknown_fields"] else None)
    accepted = sum(r.get("task_accepted") is True for r in outcomes.values())
    known_escalations = [r["escalated"] for r in outcomes.values() if r.get("escalated") is not None]
    report = {"retrospective_checkpoints": sum(r.get("retrospective") is True for r in decisions.values()), "decisions": len(decisions), "outcome_records": len(outcomes), "completed_outcomes": sum(o.get("task_accepted") is not None for o in outcomes.values()), "accepted_results": accepted,
              "child_outputs_usable": sum(r.get("child_output_usable") is True for r in outcomes.values()),
              "acceptance_unknown": sum(r.get("task_accepted") is None for r in outcomes.values()),
              "escalation_frequency": sum(known_escalations) / len(known_escalations) if known_escalations else None,
              "escalation_known": len(known_escalations), "models": models if not overlap else None,
              "overlapping_decision_intervals": overlap,
              "totals_complete": bool(decisions) and not overlap and len(measurements) == len(decisions) and all(m["complete"] for m in measurements.values()),
              "elapsed_seconds": sum(m["elapsed_seconds"] for m in measurements.values()) if not overlap and len(measurements) == len(decisions) and measurements and all(m["elapsed_seconds"] is not None for m in measurements.values()) else None,
              "coverage": {"measured_decisions": len(measurements), "complete_decisions": sum(m["complete"] for m in measurements.values()), "total_decisions": len(decisions)},
              "unpaired_legacy_records": sum(not r.get("decision_id") for r in rows if r.get("stage") in (None, "checkpoint", "outcome")),
              "subscription_savings": None, "baseline_savings": None,
              "results": [{"decision_id": identity, "tier": decisions[identity]["tier"],
                           "task_accepted": o.get("task_accepted"), "child_output_usable": o.get("child_output_usable"),
                           "escalated": o.get("escalated"), "retries": o.get("retries"), "recovery": o.get("recovery"),
                           "measurement": measurements.get(identity)} for identity, o in outcomes.items()],
              "caveat": "Tokens are observed consumption, not exact subscription allowance. Cached input is included in total input.",
              "account_snapshots": [r for r in rows if r.get("stage") == "account_snapshot"], "comparisons": []}
    for pair in [r for r in rows if r.get("stage") == "comparison"]:
        arms = {}
        for name in ("sol_only", "sol_luna"):
            identity = pair[name + "_id"]
            m = measurements.get(identity)
            o = outcomes.get(identity, {})
            accepted_arm = o.get("task_accepted") is True
            ready = m is not None and m["complete"] and accepted_arm
            arms[name] = {"decision_id": identity, "task_accepted": o.get("task_accepted"),
                          "tokens_per_accepted_result": m["models"] if ready else None,
                          "seconds_per_accepted_result": m["elapsed_seconds"] if ready else None,
                          "effort_and_cache": [{"session_id": s["session_id"], "efforts": s["efforts"], "cache_condition": s["cache_condition"]} for s in m["sessions"]] if m else None}
        a, b = measurements.get(pair["sol_only_id"]), measurements.get(pair["sol_luna_id"])
        valid_models = a and b and set(a["models"]) <= {"gpt-6.1-sol", "gpt-6-sol"} and "gpt-6-luna" in b["models"] and bool(set(b["models"]) & {"gpt-6.1-sol", "gpt-6-sol"})
        ready = bool(pair["equivalent_tasks"] is True and pair["includes_coordination_review_recovery"] is True and valid_models and all(v["tokens_per_accepted_result"] is not None for v in arms.values()))
        report["comparisons"].append({**pair, "arms": arms, "comparable_observations": ready,
                                      "elapsed_difference_seconds": (b["elapsed_seconds"] - a["elapsed_seconds"]) if ready and a["elapsed_seconds"] is not None and b["elapsed_seconds"] is not None else None,
                                      "subscription_savings": None, "note": "Observed pair only; effort, cache and concurrent work can differ. No exact subscription savings."})
    return report


def main():
    parser = argparse.ArgumentParser(description="Qualitative routing and selective subscription usage audits")
    parser.add_argument("task", nargs="?")
    parser.add_argument("--current-model")
    parser.add_argument("--work-scope", choices=("small", "substantial"), default="small")
    parser.add_argument("--independent", action="store_true")
    parser.add_argument("--input-tokens", type=int)
    parser.add_argument("--complexity", type=float)
    parser.add_argument("--task-type")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--log", type=Path)
    parser.add_argument("--retrospective", action="store_true")
    parser.add_argument("--collect", metavar="DECISION_ID", help="Audit only explicitly associated sessions")
    parser.add_argument("--summary", action="store_true")
    args = parser.parse_args()
    if args.collect or args.summary:
        if not args.log:
            parser.error("audit and summary need --log")
        result = collect_usage(args.log, args.collect) if args.collect else summarize_usage(args.log)
    else:
        if not args.current_model:
            parser.error("routing needs --current-model")
        task = args.task if args.task is not None else sys.stdin.read().strip()
        if not task:
            parser.error("provide a short deliverable summary")
        context = {"current_model": args.current_model, "work_scope": args.work_scope, "independent": args.independent}
        if args.task_type:
            context["assessment"] = {"task_type": args.task_type, "complexity": args.complexity if args.complexity is not None else (0.25 if args.task_type in DEFAULT_CONFIG["cheap_task_types"] else 0.5), "confidence": 1.0}
        if args.input_tokens is not None:
            context["input_tokens"] = args.input_tokens
        config = json.loads(args.config.read_text(encoding="utf-8")) if args.config else None
        result = route_task(task, context, config)
        if args.log:
            record_result(result, {"stage": "checkpoint", "retrospective": args.retrospective}, config={"log_path": args.log})
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
