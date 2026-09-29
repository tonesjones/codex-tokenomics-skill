import json
import tempfile
import unittest
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parents[1] / "skills" / "tokenomics"))
from tokenomics_router import record_result, route_task, summarize_usage  # noqa: E402


PRICED = {"tiers": {
    "cheap": {"model": "cheap", "max_complexity": .34, "input_per_million": 1, "output_per_million": 2},
    "standard": {"model": "standard", "max_complexity": .74, "input_per_million": 3, "output_per_million": 4},
    "strong": {"model": "strong", "max_complexity": 1, "input_per_million": 5, "output_per_million": 6},
}, "expected_output_tokens": {"short": 100, "normal": 200, "long": 400}}


def signals(task_type, complexity, confidence=0.9, bucket="normal"):
    return {"classifier": lambda task, context: {"task_type": task_type, "complexity": complexity, "confidence": confidence, "expected_output_bucket": bucket}}


class TokenomicsRouterTests(unittest.TestCase):
    def test_cheap_and_strong_routing(self):
        self.assertEqual(route_task("x", config={**PRICED, **signals("search", .1)})["model"], "cheap")
        self.assertEqual(route_task("x", config={**PRICED, **signals("architecture", .9)})["model"], "strong")

    def test_low_confidence_escalates_one_tier(self):
        decision = route_task("x", config={**PRICED, **signals("search", .1, .2)})
        self.assertEqual(decision["tier"], "standard")

    def test_classifier_failure_and_forced_model(self):
        def broken(*args): raise RuntimeError("offline")
        fallback = route_task("ordinary task", config={**PRICED, "classifier": broken})
        self.assertEqual(fallback["tier"], "standard")  # unknown has a stable standard fallback
        self.assertFalse(fallback["classifier_available"])
        self.assertEqual(route_task("x", context={"force_model": "manual"}, config=PRICED)["model"], "manual")

    def test_cost_math_and_unknown_pricing(self):
        decision = route_task("1234", config={**PRICED, **signals("search", .1, bucket="short")})
        self.assertEqual(decision["estimated_cost_usd"], round((decision["estimated_input_tokens"] + 200) / 1_000_000, 8))
        self.assertIsNone(route_task("x", context={"force_model": "not-priced"}, config=PRICED)["estimated_cost_usd"])

    def test_usage_logging_and_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "usage.jsonl"
            decision = route_task("x", config={**PRICED, **signals("search", .1)})
            record = record_result(decision, {"actual_input_tokens": 10, "actual_output_tokens": 100, "actual_cost_usd": .00021, "retry": False}, True, {"log_path": log})
            self.assertEqual(json.loads(log.read_text())["model"], "cheap")
            self.assertEqual(record["success"], True)
            self.assertEqual(summarize_usage(log)["cheap_model_success_rate"], 1.0)


if __name__ == "__main__":
    unittest.main()
