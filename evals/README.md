# Evaluation Datasets

This directory contains offline, sanitized eval datasets for Interview Agent.

Rules:

- Use synthetic or manually written samples only.
- Do not include real user answers.
- Do not include phone numbers, tokens, secrets, API keys, prompts, completions or private company data.
- Keep v1 datasets small and deterministic.
- Store generated eval reports under `evals/results/`; that directory is ignored by git.

## Dataset Shape

Each JSONL row includes:

- `case_id`
- `question`
- `candidate_answer_sanitized`
- `tags`
- `difficulty`
- `rubric_version_ref`
- `expected_score_min`
- `expected_score_max`
- `expected_strength_tags`
- `expected_weakness_tags`
- `notes`
- `reference_answer_sanitized`

## Run Mock Eval

From the repository root:

```powershell
.\scripts\run-eval.ps1
```

The default run uses `mock/local-eval` through the LLM Gateway. It does not call an external provider.
