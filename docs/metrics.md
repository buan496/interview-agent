# Metrics Foundation

PR #47 adds a Prometheus-compatible metrics foundation for Interview Agent. The goal is operational visibility for request volume, latency, errors, abuse protection, LLM usage and dependency readiness. This PR does not add Grafana, alert rules, external monitoring SaaS, OpenTelemetry tracing or production deployment.

## Endpoint

- Path: `GET /metrics`
- Format: Prometheus text exposition format.
- Content type: `text/plain; version=0.0.4; charset=utf-8`
- Config:
  - `METRICS_ENABLED=true`
  - `METRICS_PATH=/metrics`
  - `METRICS_INCLUDE_READY_GAUGES=true`
  - `METRICS_PROTECT_IN_PRODUCTION=true`

When `METRICS_ENABLED=false`, `/metrics` returns 404. When `APP_ENV=production` and `METRICS_PROTECT_IN_PRODUCTION=true`, direct access returns 403. Production should expose metrics only through an internal network, sidecar, gateway allowlist or scrape job with access control.

## Metric List

HTTP metrics:

- `interview_agent_http_requests_total{method,route,status_class}`
- `interview_agent_http_request_duration_seconds_bucket{method,route,le}`
- `interview_agent_http_request_duration_seconds_sum{method,route}`
- `interview_agent_http_request_duration_seconds_count{method,route}`
- `interview_agent_http_exceptions_total{route,status_class}`

Training business metrics:

- `interview_agent_sessions_created_total{mode}`
- `interview_agent_answers_submitted_total{mode}`
- `interview_agent_reports_generated_total{status}`
- `interview_agent_memories_created_total{memory_type}`
- `interview_agent_memory_refresh_total{status,trigger}`
- `interview_agent_async_jobs_created_total{job_type}`
- `interview_agent_async_jobs_completed_total{job_type,status}`
- `interview_agent_async_job_duration_seconds_bucket{job_type,le}`
- `interview_agent_async_jobs_in_progress{job_type}`

Abuse-protection metrics:

- `interview_agent_rate_limit_exceeded_total{scope}`
- `interview_agent_quota_exceeded_total{quota_type}`

LLM usage metrics:

- `interview_agent_llm_calls_total{provider,model,feature,status}`
- `interview_agent_llm_tokens_total{provider,model,feature,token_type}`
- `interview_agent_llm_estimated_cost_total{provider,model,feature,currency}`
- `interview_agent_llm_latency_seconds_bucket{provider,model,feature,le}`
- `interview_agent_llm_latency_seconds_sum{provider,model,feature}`
- `interview_agent_llm_latency_seconds_count{provider,model,feature}`

Dependency readiness metrics:

- `interview_agent_dependency_ready{dependency="db"}`
- `interview_agent_dependency_ready{dependency="redis"}`

Dependency gauges are updated by `/ready` when `METRICS_INCLUDE_READY_GAUGES=true`.

## Label Safety

Metrics labels must stay low-cardinality and non-sensitive. The current implementation allows only stable operational labels:

- HTTP: `method`, normalized `route`, `status_class`
- Training: `mode`, `status`, `memory_type`, `trigger`
- Async jobs: `job_type`, `status`
- Rate limit: normalized `scope`
- Quota: normalized `quota_type`
- LLM: `provider`, `model`, `feature`, `status`, `token_type`, `currency`
- Ready gauge: `dependency`

The implementation intentionally does not label metrics with:

- `request_id`
- `user_id`
- `session_id`
- phone numbers
- bearer tokens
- verification codes
- secrets or API keys
- prompt text
- model completion text
- user answer text

Dynamic route segments are normalized, for example `/api/sessions/42/answer` becomes `/api/sessions/{id}/answer`.

## LLM Usage Integration

LLM usage metrics are emitted from the same path that writes `llm_usage_records`. This keeps metrics aligned with the usage ledger:

- Successful and failed LLM attempts increment `interview_agent_llm_calls_total`.
- Prompt, completion and total tokens increment `interview_agent_llm_tokens_total`.
- Estimated cost increments `interview_agent_llm_estimated_cost_total`.
- Latency is recorded in `interview_agent_llm_latency_seconds`.
- LLM Gateway primary and fallback attempts are recorded with the actual provider/model/feature/status attempted.

Cost values are estimates using the current pricing version. They are not billing records. Prompt, completion and user answer bodies are never stored in the metrics endpoint. Gateway metrics do not include fallback booleans, request ids, user ids, session ids or raw route keys beyond low-cardinality provider/model/feature labels.

## Rate Limit and Quota Integration

Rate-limit and quota metrics are emitted at the exception boundary:

- `RateLimitExceeded` increments `interview_agent_rate_limit_exceeded_total`.
- `QuotaExceeded` increments `interview_agent_quota_exceeded_total`.

The metrics use normalized scopes such as `login_ip`, `login_phone`, `answer_submit`, `daily_tokens`, `monthly_tokens` and `daily_calls`. They do not expose limiter keys, phone numbers, user identifiers or session identifiers.

## Agent Memory Integration

Agent Memory v1 emits aggregate counters from the rule-based backend refresh path:

- `interview_agent_memories_created_total{memory_type}` increments only when a new memory row is created.
- `interview_agent_memory_refresh_total{status,trigger}` records refresh attempts such as report-triggered refreshes, manual refreshes, skipped refreshes and failed refreshes.

These metrics are operational counters only. They do not expose `user_id`, `memory_id`, `session_id`, `request_id`, tag names, answer text, prompt text, completion text, tokens or secrets.

## Async Job Integration

Async Job Queue v1 emits aggregate worker metrics:

- `interview_agent_async_jobs_created_total{job_type}` increments when the API creates a job.
- `interview_agent_async_jobs_completed_total{job_type,status}` increments when a job reaches `succeeded` or terminal `failed`.
- `interview_agent_async_job_duration_seconds{job_type}` observes worker execution duration.
- `interview_agent_async_jobs_in_progress{job_type}` tracks currently running jobs.

Async job metrics intentionally do not label by `job_id`, `user_id`, `request_id`, phone number, idempotency key, prompt text, completion text or answer text.

## Prometheus Scrape Example

Example staging scrape configuration:

```yaml
scrape_configs:
  - job_name: interview-agent-api-staging
    metrics_path: /metrics
    static_configs:
      - targets:
          - api:8000
```

For production, do not expose `/metrics` publicly. Place it behind an internal network path or gateway rule and keep `METRICS_PROTECT_IN_PRODUCTION=true` unless the deployment layer provides a safe authenticated scrape path.

## Troubleshooting

1. Use `/health` to confirm the API process is alive.
2. Use `/ready` to update and inspect dependency readiness.
3. Use `/metrics` for aggregate symptoms such as 5xx rate, latency, 429 rate, quota refusals and LLM failure spikes.
4. Use `X-Request-ID` and structured logs for request-level debugging.
5. Use `audit_events` for security/admin event reconstruction.
6. Use `llm_usage_records` for per-user usage summary and cost estimation.
7. Use `agent_memories` only for current-user training memory inspection and rule debugging; metrics remain aggregate.
8. Use `async_jobs` and worker logs for asynchronous task status and retry debugging; metrics remain aggregate.

Metrics are intentionally aggregate telemetry. They are not a replacement for request logs, audit logs or the LLM usage ledger.

## Alert Rules

PR #51 adds example Prometheus alert rules in `observability/prometheus/alerts/interview-agent-alerts.yml`.

The rules cover:

- API 5xx rate, p95 latency and missing traffic symptoms.
- Database and Redis readiness gauges.
- LLM failure rate, p95 latency and estimated-cost spike.
- Rate-limit and quota denial spikes.
- Async job failure and stuck-running symptoms.

The alert expressions intentionally use only current metric names. Future signals such as explicit fallback spike counters or queue depth are left as TODO comments until the application exposes low-cardinality metrics for them.

Run a local basic file check with:

```powershell
.\scripts\check-alert-rules.ps1
```

Promtool validation can be added by an operator environment later, but this repository does not require Prometheus or promtool in CI.

## Current Limitations

- No Grafana dashboard is included.
- Alert rules are examples only; no production Prometheus or Alertmanager deployment is included.
- No OpenTelemetry tracing is included.
- No external monitoring SaaS is integrated.
- No vector-memory, RAG-memory or Multi-Agent telemetry is included.
- Production scrape authentication must be implemented by the deployment environment or gateway.
