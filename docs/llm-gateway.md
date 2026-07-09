# LLM Gateway and Model Router v1

PR #49 adds a backend LLM Gateway foundation. The goal is to keep business code from binding directly to a concrete provider/model and to make model calls observable, metered and routeable by feature.

## Why Gateway

Before this PR, the answer scoring path could instantiate a concrete LLM client directly. That made provider/model changes harder to govern and made fallback behavior provider-specific. The gateway centralizes:

- provider abstraction
- feature-based routing
- primary/fallback model selection
- timeout and retry configuration
- normalized error handling
- usage/metrics correlation

This is a backend foundation only. It does not add a model-management frontend, tenant-specific model policy, commercial billing, external gateway service or model registry database.

## Provider Abstraction

Implemented providers:

- `mock`: stable local/test provider backed by the existing fallback behavior.
- `deepseek`: DeepSeek-compatible chat completions provider.
- `openai_compatible`: reserved adapter shape for OpenAI-compatible HTTP APIs; v1 reuses the same compatible request path.

Provider calls receive chat messages but do not persist prompt text, completion text or user answer text.

## Feature Routing

Gateway routes are configured with `provider/model` strings:

- `LLM_ROUTE_INTERVIEW_SCORING`
- `LLM_ROUTE_REPORT_SUMMARY`
- `LLM_ROUTE_MEMORY_REFRESH`
- `LLM_ROUTE_RUBRIC_VALIDATION`

Known feature names:

- `interview_scoring`
- `report_generation`
- `memory_refresh`
- `rubric_validation`
- `admin_operation`

If a feature route is empty, the gateway uses `LLM_DEFAULT_PROVIDER` and `LLM_DEFAULT_MODEL`. If those are empty, it falls back to the legacy `LLM_PROVIDER` and `DEEPSEEK_MODEL` settings.

## Fallback Strategy

Fallback is controlled by:

- `LLM_FALLBACK_ENABLED`
- `LLM_FALLBACK_PROVIDER`
- `LLM_FALLBACK_MODEL`

When the primary route fails, the gateway tries the fallback route if enabled and different from the primary route. Each primary/fallback attempt is recorded in memory for the caller so the session flow can write usage records and metrics for both failed and successful attempts.

If all routes fail, the gateway raises a normalized `LLMResponseError`. The existing interview engine still falls back to local deterministic scoring so the answer/report flow can continue.

## Timeout and Retry

Settings:

- `LLM_TIMEOUT_SECONDS`
- `LLM_MAX_RETRIES`

v1 uses a simple bounded retry loop per route. Retries are intentionally conservative; production should tune retries based on provider latency and duplicate-call cost.

## Usage and Metrics

The session scoring path records gateway attempts through the existing LLM usage ledger:

- failed primary attempt: `status=failed`
- successful fallback attempt: `status=success`, `fallback=true` in gateway attempt state
- feature: `interview_scoring`
- provider/model: actual route attempted

Metrics continue to use:

- `interview_agent_llm_calls_total{provider,model,feature,status}`
- `interview_agent_llm_tokens_total{provider,model,feature,token_type}`
- `interview_agent_llm_estimated_cost_total{provider,model,feature,currency}`
- `interview_agent_llm_latency_seconds{provider,model,feature}`

The metrics and usage ledger do not store prompt, completion or answer bodies.

## Offline Evaluation Harness

PR #55 adds an offline evaluation harness that calls model routes through LLM Gateway. The harness defaults to `mock/local-eval` and does not call external providers in CI.

Evaluation reports include provider, model, feature, fallback usage, latency and estimated cost. They do not store prompt text, completion text or real user answer text.

Use [Evaluation Harness](evaluation-harness.md) before changing feature routes such as `LLM_ROUTE_INTERVIEW_SCORING`.

## Security and Redaction

Do not log or persist:

- raw user answer text
- prompt text
- model completion text
- bearer tokens
- API keys
- verification codes
- full phone numbers

Config summaries only expose provider/model names, feature route names and whether API keys are configured.

## Configuration Example

Local development:

```env
LLM_GATEWAY_ENABLED=true
LLM_DEFAULT_PROVIDER=deepseek
LLM_DEFAULT_MODEL=deepseek-chat
LLM_FALLBACK_ENABLED=true
LLM_FALLBACK_PROVIDER=mock
LLM_FALLBACK_MODEL=local-fallback
LLM_ROUTE_INTERVIEW_SCORING=deepseek/deepseek-chat
LLM_MAX_RETRIES=1
```

Staging can use the same settings. If `DEEPSEEK_API_KEY` is empty, primary DeepSeek calls fail and the mock fallback keeps the release-candidate flow runnable. Production with a real provider must configure the required provider API key and must not rely on missing-key fallback as normal operation.

## Future Work

- Database-backed model registry.
- Admin model policy console.
- Cost-aware routing.
- Canary routing and A/B testing.
- Tenant-specific model policy after organization boundaries exist.
- Provider health scoring and circuit breaker.
