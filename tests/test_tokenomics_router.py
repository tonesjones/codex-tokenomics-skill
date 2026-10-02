import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1] / "skills" / "tokenomics"))
from tokenomics_router import estimate_tokens, record_result, route_task, summarize_usage  # noqa: E402


PRICED = {"tiers": {
    "cheap": {"model": "cheap", "max_complexity": .34, "input_per_million": 1, "output_per_million": 2},
    "standard": {"model": "standard", "max_complexity": .74, "input_per_million": 3, "output_per_million": 4},
    "strong": {"model": "strong", "max_complexity": 1, "input_per_million": 5, "output_per_million": 6},
}, "expected_output_tokens": {"short": 100, "normal": 200, "long": 3000}}


def signals(task_type, complexity, confidence=.9, bucket="normal"):
    return {"classifier": lambda task, context: {"task_type": task_type, "complexity": complexity,
                                                   "confidence": confidence, "expected_output_bucket": bucket}}


class TokenomicsRouterTests(unittest.TestCase):
    def test_word_boundaries_and_default_tiers(self):
        for task in ("Redesign button color", "Plan the database migration",
                     "Update the information panel", "Rename var in a design doc"):
            with self.subTest(task=task):
                decision = route_task(task, config=PRICED)
                self.assertEqual(decision["candidate_tier"], "standard")
                self.assertEqual(decision["action"], "stay")
        test_work = route_task("Add a unit test", config=PRICED)
        self.assertEqual(test_work["task_type"], "test")
        self.assertEqual(test_work["candidate_tier"], "cheap")

    def test_handoff_cost_can_keep_small_work_in_current_model(self):
        decision = route_task("Add a unit test", config=PRICED)
        self.assertEqual(decision["action"], "stay")
        self.assertEqual(decision["model"], "standard")
        self.assertEqual(decision["estimates"]["cheap"]["handoff_input_tokens"], 10500)
        self.assertGreater(decision["estimates"]["cheap"]["estimated_cost_usd"],
                           decision["estimates"]["stay"]["estimated_cost_usd"])

    def test_tiny_task_stays_even_when_cheap_tier_is_much_cheaper(self):
        prices = {"tiers": {"cheap": {"input_per_million": .5, "output_per_million": 2},
                            "standard": {"input_per_million": 2, "output_per_million": 8},
                            "strong": {"input_per_million": 10, "output_per_million": 30}}}
        decision = route_task("Fix typo in README", context={"current_model": "gpt-6.1-sol"}, config=prices)
        self.assertEqual((decision["candidate_tier"], decision["action"]), ("cheap", "stay"))
        self.assertIsNotNone(decision["estimates"]["cheap"]["parent_overhead_usd"])

    def test_unpriced_substantial_independent_work_can_delegate(self):
        task = "Summarize test failures"
        self.assertEqual(route_task(task)["action"], "stay")
        coupled = route_task(task, context={"work_scope": "substantial", "independent": False})
        self.assertEqual(coupled["action"], "stay")
        bounded = route_task(task, context={"work_scope": "substantial", "independent": True})
        self.assertEqual((bounded["action"], bounded["model"]), ("delegate", "gpt-6-luna"))
        self.assertIsNone(bounded["estimated_cost_usd"])
        self.assertIn("dollar savings unverified", bounded["reason"])

    def test_command_line_route(self):
        script = Path(__file__).parents[1] / "skills" / "tokenomics" / "tokenomics_router.py"
        result = subprocess.run([sys.executable, str(script), "--current-model", "gpt-6.1-sol",
                                 "--work-scope", "substantial", "--independent", "Summarize test failures"],
                                capture_output=True, text=True, check=True)
        decision = json.loads(result.stdout)
        self.assertEqual((decision["action"], decision["model"]), ("delegate", "gpt-6-luna"))
        assessed = subprocess.run([sys.executable, str(script), "--current-model", "gpt-6.1-sol",
                                   "--work-scope", "substantial", "--independent", "--task-type",
                                   "source_collection", "Collect bounded evidence for Sol"],
                                  capture_output=True, text=True, check=True)
        self.assertEqual(json.loads(assessed.stdout)["action"], "delegate")

    def test_source_collection_routes_cheap_but_interpretation_stays_standard(self):
        task = ("Collect current authoritative ADP and injury sources for fantasy basketball "
                "players, map source names to existing player IDs, and report unresolved gaps")
        context = {"current_model": "gpt-6.1-sol", "work_scope": "substantial", "independent": True}
        collection = route_task(task, context=context)
        self.assertEqual((collection["task_type"], collection["action"], collection["model"]),
                         ("source_collection", "delegate", "gpt-6-luna"))
        judgment = route_task("Collect sources and decide which injury flags to change", context=context)
        self.assertEqual((judgment["task_type"], judgment["action"], judgment["model"]),
                         ("integration", "stay", "gpt-6.1-sol"))

    def test_large_cheap_work_delegates_when_savings_survive_handoff(self):
        decision = route_task("Add a unit test", context={"input_tokens": 10000, "work_scope": "substantial", "independent": True}, config=PRICED)
        self.assertEqual((decision["action"], decision["model"]), ("delegate", "cheap"))
        self.assertEqual(decision["estimated_input_tokens"], 20500)
        self.assertEqual(decision["estimated_cost_usd"], .0255)
        self.assertEqual(decision["estimates"]["stay"]["estimated_cost_usd"], .0304)

    def test_standard_policy_and_explicit_strong(self):
        for task_type in ("architecture", "security", "hard_debugging", "integration"):
            with self.subTest(task_type=task_type):
                decision = route_task("work", config={**PRICED, **signals(task_type, .95)})
                self.assertEqual(decision["candidate_tier"], "standard")
        strong = route_task("architecture work", context={"force_strong": True}, config=PRICED)
        self.assertEqual((strong["action"], strong["model"], strong["candidate_model"]),
                         ("request_approval", "standard", "strong"))
        approved = route_task("architecture work", context={"force_strong": True, "approval_granted": True}, config=PRICED)
        self.assertEqual((approved["action"], approved["model"]), ("delegate", "strong"))

    def test_cheap_category_cannot_override_high_complexity(self):
        result = route_task("work", config={**PRICED, **signals("test", .99)})
        self.assertEqual(result["candidate_tier"], "standard")

    def test_strong_configuration_and_forced_model_request_approval(self):
        for config, context in (({"force_strong_task_types": ["unknown"]}, {}),
                                ({}, {"force_model": "strong"})):
            with self.subTest(config=config, context=context):
                result = route_task("work", context=context, config={**PRICED, **config})
                self.assertEqual(result["action"], "request_approval")
                self.assertEqual(result["candidate_model"], "strong")

    def test_approval_flag_does_not_turn_low_confidence_into_strong_route(self):
        result = route_task("work", context={"approval_granted": True},
                            config={**PRICED, **signals("design", .5, .2)})
        self.assertEqual(result["candidate_tier"], "standard")
        self.assertEqual(result["action"], "stay")

    def test_low_confidence_and_classifier_failure(self):
        low = route_task("work", config={**PRICED, **signals("test", .1, .2)})
        self.assertEqual(low["candidate_tier"], "standard")
        self.assertEqual(low["action"], "stay")

        def broken(*args):
            raise RuntimeError("offline")

        fallback = route_task("ordinary task", config={**PRICED, "classifier": broken})
        self.assertEqual((fallback["action"], fallback["candidate_tier"]), ("stay", "standard"))
        self.assertFalse(fallback["classifier_available"])
        from_cheap = route_task("ordinary task", context={"current_model": "gpt-6-luna"})
        self.assertEqual((from_cheap["action"], from_cheap["model"]), ("delegate", "gpt-6.1-sol"))

    def test_cost_options_unknown_pricing_and_force_model(self):
        context = {"input_tokens": 1000, "handoff_context_tokens": 600, "handoff_read_tokens": 400}
        decision = route_task("Add a unit test", context=context, config=PRICED)
        self.assertEqual(decision["estimates"]["stay"]["estimated_cost_usd"], .0034)
        self.assertEqual(decision["estimates"]["cheap"]["estimated_cost_usd"], .007)
        self.assertEqual(decision["estimates"]["strong"]["estimated_cost_usd"], .0154)
        unpriced = route_task("Add a unit test")
        self.assertEqual(unpriced["action"], "stay")
        self.assertTrue(all(option["estimated_cost_usd"] is None for option in unpriced["estimates"].values()))
        forced = route_task("work", context={"force_model": "unlisted"}, config=PRICED)
        self.assertEqual((forced["action"], forced["model"], forced["estimated_cost_usd"]),
                         ("delegate", "unlisted", None))
        self.assertIsNone(forced["estimates"]["forced"]["estimated_cost_usd"])
        self.assertIn("pricing unavailable", forced["reason"])

    def test_zero_child_handoff_still_charges_parent_overhead(self):
        result = route_task("work", context={"handoff_context_tokens": 0, "handoff_read_tokens": 0}, config=PRICED)
        self.assertIsNotNone(result["estimates"]["cheap"]["parent_overhead_usd"])
        self.assertEqual(result["estimates"]["cheap"]["handoff_input_tokens"], 0)
        self.assertIsNone(result["estimates"]["stay"]["parent_overhead_usd"])

    def test_parent_remaining_input_is_charged_separately(self):
        result = route_task("work", context={"parent_remaining_input_tokens": 1000}, config=PRICED)
        expected = (1000 + 1500 + 200) * 3 / 1_000_000
        self.assertEqual(result["estimates"]["cheap"]["parent_overhead_usd"], round(expected, 8))

    def test_compact_child_input_can_make_delegation_pay(self):
        prices = {"tiers": {"cheap": {"input_per_million": 5, "output_per_million": 1},
                            "standard": {"input_per_million": 1, "output_per_million": 2},
                            "strong": {"input_per_million": 10, "output_per_million": 6}},
                  "handoff_context_tokens": 0, "handoff_read_tokens": 0, "parent_handoff_tokens": 0}
        scope = {"input_tokens": 10000, "work_scope": "substantial", "independent": True}
        without_compaction = route_task("work", scope, {**prices, **signals("test", .2)})
        compact = route_task("work", {**scope, "child_input_tokens": 1000},
                             {**prices, **signals("test", .2)})
        self.assertEqual(without_compaction["action"], "stay")
        self.assertEqual(compact["action"], "delegate")
        self.assertEqual(compact["estimates"]["cheap"]["base_input_tokens"], 1000)
        self.assertEqual(compact["estimates"]["cheap"]["input_token_source"], "provided child_input_tokens")

    def test_cached_input_rate_changes_estimate_and_missing_rate_is_unknown(self):
        prices = {"tiers": {"cheap": {"input_per_million": 3, "output_per_million": 2,
                                        "cached_input_per_million": .1},
                            "standard": {"input_per_million": 2, "output_per_million": 2},
                            "strong": {"input_per_million": 10, "output_per_million": 6}},
                  "handoff_context_tokens": 0, "handoff_read_tokens": 0, "parent_handoff_tokens": 0}
        context = {"input_tokens": 10000, "child_cached_input_tokens": 10000,
                   "work_scope": "substantial", "independent": True}
        known = route_task("work", context, {**prices, **signals("test", .2)})
        self.assertEqual(known["action"], "delegate")
        self.assertEqual(known["estimates"]["cheap"]["cached_input_tokens"], 10000)

        unknown_price = {**prices, "tiers": {**prices["tiers"],
                          "cheap": {"input_per_million": 3, "output_per_million": 2}}}
        unknown = route_task("work", context, {**unknown_price, **signals("test", .2)})
        self.assertIsNone(unknown["estimates"]["cheap"]["estimated_cost_usd"])
        self.assertIn("dollar savings unverified", unknown["reason"])

    def test_warm_sol_context_can_make_staying_cheaper(self):
        prices = {"tiers": {"cheap": {"input_per_million": 1, "output_per_million": 2},
                            "standard": {"input_per_million": 3, "cached_input_per_million": .1,
                                         "output_per_million": 4},
                            "strong": {"input_per_million": 5, "output_per_million": 6}}}
        context = {"input_tokens": 20000, "work_scope": "substantial", "independent": True}
        cold = route_task("work", context, {**prices, **signals("test", .2)})
        warm = route_task("work", {**context, "stay_cached_input_tokens": 18000},
                          {**prices, **signals("test", .2)})
        self.assertEqual(cold["action"], "delegate")
        self.assertEqual(warm["action"], "stay")
        self.assertEqual(warm["estimates"]["stay"]["cached_input_tokens"], 18000)

    def test_small_savings_do_not_pay_for_handoff_uncertainty(self):
        prices = {"tiers": {"cheap": {"input_per_million": 1, "output_per_million": 2},
                            "standard": {"input_per_million": 1.05, "output_per_million": 2.1},
                            "strong": {"input_per_million": 5, "output_per_million": 6}},
                  "handoff_context_tokens": 0, "handoff_read_tokens": 0, "parent_handoff_tokens": 0,
                  "minimum_savings_fraction": .15}
        result = route_task("work", {"input_tokens": 10000, "work_scope": "substantial", "independent": True},
                            {**prices, **signals("test", .2)})
        self.assertEqual(result["action"], "stay")

    def test_unknown_tiktoken_model_uses_documented_approximation(self):
        fake = SimpleNamespace(encoding_for_model=lambda model: (_ for _ in ()).throw(KeyError(model)))
        with patch.dict(sys.modules, {"tiktoken": fake}):
            self.assertEqual(estimate_tokens("abcdefgh", "unlisted"), (2, "chars/4 approximation"))

    def test_configured_strong_override_and_alias_prices(self):
        for key in ("force_strong_task_types", "high_value_task_types"):
            result = route_task("work", config={key: ["unknown"]})
            self.assertEqual((result["action"], result["model"], result["candidate_model"]),
                             ("request_approval", "gpt-6.1-sol", "gpt-6-astra"))
        result = route_task("Collect sources", {"current_model": "gpt-6-sol", "work_scope": "substantial", "independent": True},
                            {"tiers": {"standard": {"input_per_million": 2, "output_per_million": 8}}})
        self.assertIsNone(result["estimates"]["stay"]["estimated_cost_usd"])

    def test_current_sol_alias_and_judgment(self):
        context = {"current_model": "gpt-6.1-sol", "work_scope": "substantial", "independent": True}
        result = route_task("Collect sources", context)
        self.assertEqual((result["action"], result["model"]), ("delegate", "gpt-6-luna"))
        for task in ("Summarize sources and recommend which stock to sell", "Add tests and decide whether authentication is safe"):
            self.assertEqual(route_task(task, context)["action"], "stay")

    def test_agent_assessment_and_priced_scope_gate(self):
        context = {"current_model": "gpt-6.1-sol", "work_scope": "substantial", "independent": True,
                   "assessment": {"task_type": "source_collection", "confidence": .9, "complexity": .3}}
        self.assertEqual(route_task("Research current ADP and injury reports", context)["action"], "delegate")
        for independent in (False, True):
            result = route_task("Summarize files", {"input_tokens": 100000, "work_scope": "small", "independent": independent}, PRICED)
            self.assertEqual(result["action"], "stay")

    def test_usage_logging_and_summary(self):
        with tempfile.TemporaryDirectory() as directory:
            log = Path(directory) / "usage.jsonl"
            decision = route_task("Add a unit test", context={"input_tokens": 10000, "work_scope": "substantial", "independent": True}, config=PRICED)
            record = record_result(decision, {"actual_input_tokens": 10000, "actual_output_tokens": 100,
                                              "actual_cost_usd": .0102, "retry": False}, True, {"log_path": log})
            self.assertEqual(json.loads(log.read_text())["action"], "delegate")
            self.assertTrue(record["success"])
            summary = summarize_usage(log)
            self.assertEqual(summary["cheap_model_success_rate"], 1.0)
            self.assertIn("cost_mean_absolute_relative_error", summary)


if __name__ == "__main__":
    unittest.main()
