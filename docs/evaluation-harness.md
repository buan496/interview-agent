# Evaluation Harness and Model Comparison v1

PR #55 adds an offline evaluation harness for Interview Agent. It helps compare LLM Gateway routes, prompt/rubric behavior, latency and estimated cost before changing model routing.

This is an offline quality gate. It is not an online A/B test, not a model-management console, and not a production traffic experiment.

## Why It Exists

LLM Gateway can route by feature and fall back between providers, but routing alone does not prove that a model is good enough for interview scoring. The harness gives the project a repeatable way to ask:

- Does the candidate route score known cases within an expected range?
- Did a rubric or prompt change regress scoring stability?
- Did latency or estimated cost increase?
- Did fallback usage or failure count increase?

## Dataset Structure

Datasets live under `evals/datasets/`.

The v1 smoke dataset is:

```text
evals/datasets/interview_scoring_smoke.jsonl
```

Each JSONL row contains `case_id`, `question`, `candidate_answer_sanitized`, `tags`, `difficulty`, `rubric_version_ref`, expected score range, expected tags, notes and a sanitized reference answer.

Dataset rules:

- Use synthetic or manually written sanitized examples.
- Do not use real user answers.
- Do not include phone numbers, tokens, secrets, API keys, prompt text, completion text or private data.
- Keep v1 datasets small and stable.

## Run Mock Eval

From the repository root:

```powershell
.\scripts\run-eval.ps1
```

The default run uses `mock/local-eval` through LLM Gateway. It does not call an external provider.

Generated reports are written under `evals/results/`, which is ignored by git.

## Run Real Provider Eval Manually

Real provider eval is opt-in only:

```powershell
$env:EVAL_ALLOW_REAL_PROVIDER = "true"
.\scripts\run-eval.ps1 `
  -Provider deepseek `
  -Model deepseek-chat `
  -UseRealProvider
```

Both `-UseRealProvider` and `EVAL_ALLOW_REAL_PROVIDER=true` are required. Do not run real provider eval in default CI.

## Compare Baseline and Candidate

After producing two JSON reports:

```powershell
Push-Location backend
python -m app.eval_runner compare `
  --baseline ..\evals\results\baseline.json `
  --candidate ..\evals\results\candidate.json
Pop-Location
```

The comparison checks pass-rate delta, latency delta, estimated cost delta, failure-count delta and fallback-count delta. If a regression is detected, the command exits with code `2`.

## Model Switch Decision

Use the harness as one input, not the only decision maker.

Minimum acceptance for a model route change:

- pass rate does not regress materially
- failure count does not increase
- fallback count is understood
- latency increase is acceptable
- estimated cost increase is acceptable
- human review accepts sample scoring behavior

## Sensitive Content Rules

The eval result does not store prompt text, completion text, real user answer text, tokens, secrets or full phone numbers.

Reports include case ids, score, expected range, provider/model, fallback flag, estimated token counts, latency and estimated cost.

## Relationship to LLM Gateway

The harness calls models through LLM Gateway. It does not instantiate DeepSeek or other providers directly.

Provider/model and fallback data are read from gateway attempts and written into the eval report.

## Relationship to Rubric Versioning

Each dataset case includes `rubric_version_ref`. v1 records this as dataset metadata and uses the current scoring prompt path. Future PRs can bind offline eval cases directly to persisted rubric versions.

## Relationship to Metrics and Usage

Offline eval does not write `llm_usage_records` by default and should not pollute user usage summaries.

When real provider eval is run manually, operators should record cost/latency in the eval report and release evidence if the result informs a route change.

## Future Work

- Larger golden datasets.
- Human review workflow.
- LLM-as-judge, with strict privacy controls.
- Rubric-specific eval suites.
- Canary rollout after production deployment exists.
- Online A/B testing after telemetry, consent and product policy are ready.
