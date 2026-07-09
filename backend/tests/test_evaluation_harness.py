from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from app.evaluation_harness import (
    EvalCaseResult,
    EvalModelConfig,
    calculate_eval_summary,
    compare_model_results,
    load_eval_dataset,
    result_to_dict,
    run_eval_suite,
    write_eval_report,
)


DATASET_PATH = Path(__file__).resolve().parents[2] / "evals" / "datasets" / "interview_scoring_smoke.jsonl"


class EvaluationHarnessTest(unittest.IsolatedAsyncioTestCase):
    async def test_dataset_loads_sanitized_cases(self) -> None:
        dataset = load_eval_dataset(DATASET_PATH)

        self.assertGreaterEqual(len(dataset.cases), 5)
        self.assertLessEqual(len(dataset.cases), 15)
        self.assertTrue(all(case.case_id for case in dataset.cases))
        joined = json.dumps([case.__dict__ for case in dataset.cases]).lower()
        for forbidden in ["authorization", "bearer ", "secret", "api_key", "sk-", "gho_"]:
            self.assertNotIn(forbidden, joined)

    async def test_mock_eval_suite_runs_through_gateway(self) -> None:
        dataset = load_eval_dataset(DATASET_PATH)
        result = await run_eval_suite(dataset, EvalModelConfig(provider="mock", model="local-eval"), eval_run_id="unit-eval")

        self.assertEqual(result.eval_run_id, "unit-eval")
        self.assertEqual(result.total_cases, len(dataset.cases))
        self.assertGreater(result.pass_count, 0)
        self.assertEqual(result.provider, "mock")
        self.assertEqual(result.model, "local-eval")
        self.assertTrue(all(case.provider == "mock" for case in result.cases))
        serialized = json.dumps(result_to_dict(result)).lower()
        self.assertNotIn("candidate_answer_sanitized", serialized)
        self.assertNotIn("completion_text", serialized)
        self.assertNotIn("answer text", serialized)
        self.assertIn("prompt_tokens_estimated", serialized)

    async def test_write_eval_report_outputs_json_and_markdown_without_answers(self) -> None:
        dataset = load_eval_dataset(DATASET_PATH)
        result = await run_eval_suite(dataset, EvalModelConfig(), eval_run_id="write-eval")

        with tempfile.TemporaryDirectory() as tmpdir:
            json_path, md_path = write_eval_report(result, tmpdir)
            self.assertTrue(json_path.exists())
            self.assertTrue(md_path.exists())
            report_text = json_path.read_text(encoding="utf-8") + md_path.read_text(encoding="utf-8")

        self.assertIn("write-eval", report_text)
        self.assertNotIn("candidate_answer_sanitized", report_text)

    async def test_missing_dataset_fails_clearly(self) -> None:
        with self.assertRaises(FileNotFoundError):
            load_eval_dataset("missing-eval-dataset.jsonl")

    async def test_real_provider_eval_is_blocked_by_default(self) -> None:
        dataset = load_eval_dataset(DATASET_PATH)

        with self.assertRaisesRegex(ValueError, "Real provider eval requires"):
            await run_eval_suite(dataset, EvalModelConfig(provider="deepseek", model="deepseek-chat"))

    async def test_compare_results_detects_regression(self) -> None:
        dataset = load_eval_dataset(DATASET_PATH)
        good_cases = [
            EvalCaseResult(
                case_id="case-a",
                passed=True,
                score=80,
                expected_score_min=70,
                expected_score_max=90,
                mastery="pass",
                action="verdict",
                provider="mock",
                model="baseline",
                fallback_used=False,
                latency_ms=10,
                prompt_tokens_estimated=10,
                completion_tokens_estimated=5,
                estimated_cost="0.000000",
            )
        ]
        bad_cases = [replace(good_cases[0], passed=False, score=20, model="candidate")]
        baseline = calculate_eval_summary(
            dataset=dataset,
            config=EvalModelConfig(provider="mock", model="baseline"),
            case_results=good_cases,
            eval_run_id="baseline",
        )
        candidate = calculate_eval_summary(
            dataset=dataset,
            config=EvalModelConfig(provider="mock", model="candidate"),
            case_results=bad_cases,
            eval_run_id="candidate",
        )

        comparison = compare_model_results(baseline, candidate)

        self.assertEqual(comparison.decision, "worse")
        self.assertTrue(comparison.regression_detected)
        self.assertIn("NO-GO", comparison.recommended_decision)


if __name__ == "__main__":
    unittest.main()
