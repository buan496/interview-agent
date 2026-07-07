# Observability Foundation

本文档说明 Interview Agent 当前的生产可观测性基础。当前目标是能快速定位请求、错误和核心训练链路问题，不接入 Sentry、Datadog 或完整 OpenTelemetry。

## Request ID

- 每个后端请求都会拥有一个 `request_id`。
- 客户端可传入 `X-Request-ID`，服务端会规范化并复用。
- 响应会返回 `X-Request-ID`，用户反馈问题时可以提供该值。
- 500 错误响应会包含 `request_id`，用于在日志中定位对应请求。

示例：

```text
X-Request-ID: support-case-20260707-001
```

## Structured Logs

后端日志使用稳定 JSON 字段，核心字段包括：

- `event_name`
- `status`
- `request_id`
- `user_id`
- `method`
- `path`
- `status_code`
- `duration_ms`
- `client_ip`
- `resource_id` 或具体资源字段，例如 `session_id`、`sq_id`、`plan_id`

示例：

```json
{"event_name":"http_request","request_id":"trace-123","method":"GET","path":"/api/me/ability-profile","status":"ok","status_code":200,"duration_ms":12.5,"user_id":7}
```

## Business Events

当前已覆盖的基础事件：

- `auth.request_code`
- `auth.login`
- `session.create`
- `session.read`
- `session.history.read`
- `answer.submit`
- `report.generate`
- `report.read`
- `wrong_book.read`
- `radar.read`
- `ability_profile.read`
- `reports.list`
- `practice_plan.read`
- `practice_plan.complete`
- `admin.*`

这些事件只记录排障必要字段，不记录用户回答正文、验证码、token、secret 或完整手机号。

## Error Response

HTTP 业务错误会保留原有状态码和 `detail`，并增加 `request_id`：

```json
{"detail":"Missing bearer token","request_id":"trace-123"}
```

未处理异常统一返回：

```json
{"detail":"Internal Server Error","request_id":"trace-123"}
```

内部异常细节只进入服务端日志，不返回给前端。

## Health Checks

- `GET /health`：轻量存活检查，不访问数据库。
- `GET /ready`：数据库就绪检查，执行 `SELECT 1`。

返回字段：

- `service`
- `status`
- `environment`

这些接口不会返回密钥、连接串或模型配置。

## Sensitive Data Rules

日志禁止记录：

- `Authorization` header
- access token
- JWT secret / token secret
- 验证码
- 完整手机号
- 用户完整回答正文

手机号如需排障，只允许使用脱敏格式，例如 `138****0000`。

## Troubleshooting Flow

1. 从用户反馈、前端响应 header 或 500 响应体中拿到 `request_id`。
2. 在后端日志中搜索该 `request_id`。
3. 查看同一 `request_id` 下的 `http_request` 和业务事件。
4. 如果是 500，查看 `http_request_exception` 的堆栈。
5. 如果是用户数据问题，优先核对 `user_id`、`session_id`、`report_id`、`plan_id`。
## LLM Usage Metering

PR #35 adds an internal LLM usage ledger that links model calls with `request_id` for troubleshooting and cost estimation. This is metering, not billing.

Recorded fields:

- `llm_usage_records` stores `user_id`, `session_id`, `request_id`, `feature`, `provider`, `model`, `prompt_tokens`, `completion_tokens`, `total_tokens`, `estimated_cost`, `pricing_version`, `latency_ms`, `status` and `error_type`.
- The answer scoring flow writes usage only when an LLM call is actually attempted. Local rule-based early returns do not create fake usage.
- DeepSeek configuration or response failures that fall back locally are recorded as failed usage with provider, model, latency and request_id.
- The current user can read usage through `GET /api/me/usage/summary`.

Sensitive data rules:

- The usage ledger does not store prompt text.
- The usage ledger does not store model completion text.
- The usage ledger does not store user answer text.
- The usage ledger does not store tokens, secrets, verification codes or full phone numbers.

Cost notes:

- `estimated_cost` is for internal estimation and engineering decisions only; it is not a bill.
- The current `pricing_version` is `llm-pricing-v1-2026-07`.
- Unknown models still record tokens, but estimated cost is 0.

## Configuration Events

PR #36 adds a `config.loaded` startup event. It is designed for operational debugging and production readiness checks, not for exposing secrets.

The event includes:

- app environment, service name and API prefix
- whether auth, LLM, SMS and audio secrets are configured
- masked database and Redis URLs
- masked admin phone numbers
- log level, log format and request id header
- LLM usage metering enablement and pricing version

The event does not include secret values, tokens, verification codes, API keys, database passwords or full phone numbers.

## Release Troubleshooting

PR #37 adds release/CD management documentation and a manual release candidate workflow. After a staging or production release, operational troubleshooting should start from release evidence and request tracing:

1. Identify the release version, commit SHA and image tag from `docs/release-evidence-template.md`.
2. Collect `X-Request-ID` from the user report, API response or support ticket.
3. Search structured logs by `request_id`.
4. For 500 errors, inspect `http_request_exception`.
5. For auth issues, inspect masked `auth.login` and `auth.request_code` events.
6. For LLM cost or failure spikes, inspect `llm_usage_records` and current-user usage summaries.
7. Confirm `/health` and `/ready` before and after rollback.

Release notes and incident records must not include tokens, secrets, verification codes, full phone numbers, prompt text or user answer text.
