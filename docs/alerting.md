# Alerting Rules

This document defines the first alerting baseline for Interview Agent. It turns the existing Prometheus-compatible metrics into actionable operations signals. It does not integrate PagerDuty, Feishu, DingTalk, Slack, Grafana, Alertmanager or a production Prometheus deployment.

## Goals

- Detect API availability, latency, dependency and worker issues before users report them.
- Detect LLM failure, latency and estimated-cost spikes early.
- Detect abuse-protection and quota anomalies without exposing user identifiers.
- Provide a severity model and evidence rules that are useful during staging and early production trials.

## Rule Files

Example Prometheus alert rules live at:

```text
observability/prometheus/alerts/interview-agent-alerts.yml
```

The rules use only existing metrics from `backend/app/metrics.py` and `docs/metrics.md`. Missing future signals, such as async queue depth and explicit fallback spike counters, are documented as TODO comments instead of being faked.

## Severity Model

| Severity | Meaning | Response target | Examples |
| --- | --- | --- | --- |
| P0 | Service unavailable, data safety risk or irreversible production impact | Immediate response | DB down, production cannot serve core API, migration risk without backup evidence |
| P1 | Core user flow severely degraded but recoverable | 15 minutes | sustained 5xx, Redis required but down, LLM all-provider failure, async job failure spike |
| P2 | Significant degradation, cost spike, capacity issue or repeated user friction | Same business day | high latency, rate-limit spike, quota spike, estimated LLM cost spike |
| P3 | Trend, hygiene or low-priority capacity issue | Planned follow-up | noisy alert, low-volume traffic anomaly, threshold tuning |

## Alert Examples

P0 examples:

- `DatabaseNotReady`
- production API unavailable
- migration planned without verified backup evidence
- restore needed without approval

P1 examples:

- `High5xxErrorRate`
- `RedisNotReady` when Redis-backed rate limit or async jobs are enabled
- `HighLLMFailureRate`
- `AsyncJobFailureSpike`

P2 examples:

- `HighRequestLatency`
- `HighLLMLatency`
- `LLMTokenCostSpike`
- `RateLimitSpike`
- `QuotaExceededSpike`
- `AsyncJobStuckRunning`

P3 examples:

- warning-level no-traffic symptoms in low-volume staging
- alert threshold tuning
- dashboard or runbook improvements

## Response Principles

- Start from the alert name, affected service, time window and severity.
- Check `/health`, `/ready` and `/metrics` from a trusted network path.
- Correlate aggregate symptoms with `X-Request-ID`, structured logs and audit events.
- For LLM issues, compare metrics with `llm_usage_records`.
- For worker issues, compare metrics with `async_jobs` rows and worker logs.
- For release regressions, compare metrics before and after the latest release candidate.
- Do not paste secrets, tokens, verification codes, full phone numbers, prompt text, completion text or user answer text into alert notes or incident records.

## Silence Policy

- Silence only the narrowest alert and label set needed.
- Always include an owner, reason and expiry time.
- Do not silence P0/P1 alerts without an active incident record.
- Do not silence dependency alerts during a release unless the release is explicitly paused.
- Convert repeated false positives into threshold or rule follow-up tasks.

## Evidence Rules

Every P0/P1 incident should record:

- incident id and severity
- alert name and first fired time
- affected service and route if known
- key metrics and time window
- request ids if available
- latest release and image tag
- actions taken and rollback decision
- backup or restore evidence if used
- owner and follow-up tasks

Use `docs/incident-evidence-template.md` for the record.

## Public Beta Gate

During an invited beta:

- Check active P0/P1 alerts before inviting users and before extending the beta window.
- Pause new invitations while P0/P1 is active.
- Record alert-rule check evidence in `docs/public-beta-evidence-template.md`.
- Treat privacy export/delete failures, auth bypass, public secret exposure, public DB/Redis exposure and public `/metrics` exposure as beta-blocking until triaged.

## Sensitive Information

Alert labels, annotations and evidence must not contain:

- `request_id`, `user_id`, `session_id` or `job_id` as metric labels
- bearer tokens
- JWT secrets
- API keys
- verification codes
- full phone numbers
- prompt text
- completion text
- user answer text

Metric labels must remain low-cardinality. Use logs and database tooling for request-level or user-level investigation after authorization.
