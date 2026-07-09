from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from app.evaluation_harness import (
    EvalModelConfig,
    compare_model_results,
    load_eval_dataset,
    load_eval_run_result,
    result_to_dict,
    run_eval_suite_sync,
    write_eval_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Interview Agent offline evaluation harness")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run = subparsers.add_parser("run", help="Run an offline eval suite")
    run.add_argument("--dataset", default="../evals/datasets/interview_scoring_smoke.jsonl")
    run.add_argument("--feature", default="interview_scoring")
    run.add_argument("--provider", default="mock")
    run.add_argument("--model", default="local-eval")
    run.add_argument("--fallback-provider", default="mock")
    run.add_argument("--fallback-model", default="local-fallback")
    run.add_argument("--disable-fallback", action="store_true")
    run.add_argument("--output-dir", default="../evals/results")
    run.add_argument("--eval-run-id", default="")
    run.add_argument("--use-real-provider", action="store_true")

    compare = subparsers.add_parser("compare", help="Compare two eval result JSON files")
    compare.add_argument("--baseline", required=True)
    compare.add_argument("--candidate", required=True)
    compare.add_argument("--output", default="")

    return parser.parse_args()


def assert_provider_allowed(provider: str, use_real_provider: bool) -> None:
    if provider.strip().lower() == "mock":
        return
    env_enabled = os.getenv("EVAL_ALLOW_REAL_PROVIDER", "").lower() in {"1", "true", "yes"}
    if not (use_real_provider and env_enabled):
        raise SystemExit(
            "Real provider eval is disabled. Pass --use-real-provider and set EVAL_ALLOW_REAL_PROVIDER=true explicitly."
        )


def main() -> None:
    args = parse_args()
    if args.command == "run":
        assert_provider_allowed(args.provider, args.use_real_provider)
        dataset = load_eval_dataset(args.dataset)
        config = EvalModelConfig(
            provider=args.provider,
            model=args.model,
            feature=args.feature,
            fallback_provider=args.fallback_provider,
            fallback_model=args.fallback_model,
            fallback_enabled=not args.disable_fallback,
            use_real_provider=args.use_real_provider,
        )
        result = run_eval_suite_sync(dataset, config, eval_run_id=args.eval_run_id or None)
        json_path, md_path = write_eval_report(result, args.output_dir)
        print(f"Eval report JSON: {json_path}")
        print(f"Eval report Markdown: {md_path}")
        print(json.dumps({
            "eval_run_id": result.eval_run_id,
            "total_cases": result.total_cases,
            "pass_count": result.pass_count,
            "fail_count": result.fail_count,
            "score_within_range_rate": result.score_within_range_rate,
            "estimated_cost": result.estimated_cost,
        }, ensure_ascii=False))
        return

    if args.command == "compare":
        baseline = load_eval_run_result(args.baseline)
        candidate = load_eval_run_result(args.candidate)
        comparison = compare_model_results(baseline, candidate)
        rendered = json.dumps(result_to_dict(comparison), ensure_ascii=False, indent=2)
        if args.output:
            Path(args.output).parent.mkdir(parents=True, exist_ok=True)
            Path(args.output).write_text(rendered + "\n", encoding="utf-8")
            print(f"Comparison report: {args.output}")
        else:
            print(rendered)
        if comparison.regression_detected:
            raise SystemExit(2)


if __name__ == "__main__":
    main()
