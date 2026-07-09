# SaaS Gap Analysis

本文档基于当前代码扫描，分析 Interview Agent 距离企业级 SaaS 的差距。结论严格区分“已完成、部分完成、未完成、建议下一步”。

## 扫描范围

- 后端：`backend/app`、`backend/tests`
- 前端：`frontend/app`、`frontend/lib`、`frontend/tests/e2e`
- 数据库：`backend/app/models.py`、`backend/alembic/versions/0001_initial_schema.py`
- 文档与工程化：`README.md`、`docs/`、`docker-compose.yml`、`.github/workflows/ci.yml`、`scripts/ci-local.ps1`

## 当前已完成能力

| 能力 | 状态 | 代码依据 |
| --- | --- | --- |
| 登录入口 | 部分完成 | `backend/app/api/auth.py` 有手机号验证码接口、环境隔离的开发验证码和 Bearer token；`frontend/app/(auth)/login/page.tsx` 有登录页 |
| 当前用户解析 | 已完成基础版 | `get_current_user` 解析 token subject，并读取或创建 `User` |
| Admin 保护 | 部分完成 | `require_admin` 基于 `ADMIN_PHONES`；`backend/app/api/admin.py` 对整个 router 使用依赖 |
| Session 绑定用户 | 已完成基础版 | `Session.user_id` 非空；创建、读取、提交、报告按 `current_user.id` 过滤 |
| Report 绑定用户 | 已完成基础版 | Report 存在 `Session.report`，读取报告时按 `Session.user_id` 过滤 |
| WrongBook 绑定用户 | 已完成基础版 | `WrongBook` 主键为 `user_id + question_id`；查询按当前用户过滤 |
| 能力统计 / 能力画像 | 部分完成 | `UserTagStat` 按 `user_id + tag_id` 记录平均分和次数；`/me/ability-profile` 聚合当前用户优势项、薄弱项和标签画像 |
| 今日计划 | 部分完成 | `PracticePlan` 按 `user_id + plan_date` 唯一；可基于错题、弱标签、报告行动项生成任务 |
| 用户数据隔离测试 | 已完成基础版 | `backend/tests/test_user_data_isolation.py` 覆盖 Session、Report、WrongBook、Radar、PracticePlan 跨用户隔离 |
| 题库与投稿 | 部分完成 | `questions`、`question_submissions`、`admin/submissions`、`admin/generate` |
| LLM fallback | 已完成基础版 | `DeepSeekLLM` 与 `MockLLM`，未配置模型时可跑通 |
| E2E 核心路径 | 已完成基础版 | `frontend/tests/e2e/core-flow.spec.ts`、`navigation.spec.ts`、`visual-smoke.spec.ts` |
| CI | 已完成基础版 | GitHub Actions 覆盖 Backend、Frontend、Migrations、Compose、Docker Build、Secret Scan |

## 重点问题结论

### 当前登录是否是真实用户体系？

状态：部分完成。

事实：

- `backend/app/api/auth.py` 会根据手机号创建或读取 `User`。
- token subject 为手机号，接口通过 Bearer token 识别当前用户。
- 开发/测试环境可通过 `AUTH_DEV_CODE_ENABLED` 和 `AUTH_DEV_CODE` 使用开发验证码，`request-code` 仅在非生产环境返回 `development_code`。
- `APP_ENV=production` 时会拒绝默认开发验证码 `000000` 和默认 `JWT_SECRET`。
- token 过期时间可通过 `ACCESS_TOKEN_EXPIRE_MINUTES` 配置，登录 token payload 包含 `sub` 和 `uid`。

缺口：

- 没有真实短信服务集成；生产环境当前不会静默接受任何验证码。
- 没有验证码发送记录、验证码存储、验证码过期校验、错误次数限制和重放保护。
- 没有 refresh token、设备管理、退出登录服务端撤销。
- token 是自定义 HMAC 格式，不是标准 JWT/OIDC 实现。

建议下一步：

- PR #31 已补充 User data isolation regression tests，固化已有用户数据边界。
- 后续认证增强：接入真实短信服务、验证码存储、过期、错误次数、rate limit、标准 JWT 或 OIDC。

### 后端数据是否按 user_id 隔离？

状态：大部分训练数据已完成基础隔离。

事实：

- `Session.user_id` 创建时写入 `current_user.id`。
- `get_session`、`get_report`、`answer` 查询均要求 `Session.user_id == current_user.id`。
- `_answer_stream` 二次校验 `sq.session.user_id != user_id` 时拒绝。
- `WrongBook`、`UserTagStat`、`PracticePlan` 都包含 `user_id`。
- `stats.py` 中 wrong-book、radar、reports 均按当前用户过滤。
- `backend/tests/test_user_data_isolation.py` 已覆盖 A 用户无法读取或写入 B 用户 Session/Report，并验证 wrong-book、radar、reports、practice-plan 只返回当前 token 用户数据。

缺口：

- 题库是全局共享，没有 tenant/organization 维度。
- 投稿 `QuestionSubmission` 没有绑定提交用户 id，仅有 `submitter_name`。
- 已有系统级回归测试覆盖“用户 A 不能访问用户 B 的 Session/Report/WrongBook/UserTagStat/PracticePlan”基础场景。
- 没有租户级隔离。

建议下一步：

- PR #34：Organization and tenant model。再引入组织/租户维度。

### Session / Report / WrongBook 是否绑定真实用户？

状态：基础绑定已完成。

事实：

- `Session.user_id` 非空。
- `EvaluationResult.user_id` 非空。
- `WrongBook.user_id` 是复合主键一部分。
- `PracticePlan.user_id` 非空。
- `Report` 当前存储在 `Session.report` 中，通过 Session 用户隔离。

缺口：

- Report 没有独立表，无法独立版本化、审计、导出、锁定。
- `Message` 和 `SessionQuestion` 没有直接 user_id，依赖 Session 关联隔离。
- 没有报告访问审计。

建议下一步：

- 后续报告边界 PR：增加独立 Report 表设计、报告版本化、审计和导出能力。

### 是否存在 demo user、mock user、硬编码用户？

状态：未发现后端 demo user 数据路径；存在受环境控制的开发验证码和 E2E mock 数据。

事实：

- 后端 `auth.py` 根据手机号创建真实 `User` 行。
- 没有 `_demo_user` 函数。
- E2E 使用 `frontend/tests/e2e/helpers/core-fixtures.ts` mock API 响应，这是测试层数据。
- `request-code` 仅在非生产开发验证码开启时返回 `development_code`，默认值来自 `AUTH_DEV_CODE`。
- `login` 通过 `verify_sms_code` 校验验证码；开发验证码由 `AUTH_DEV_CODE_ENABLED` 和 `AUTH_DEV_CODE` 控制。
- `APP_ENV=production` 会阻止默认 `000000` 开发验证码和默认 token secret。

缺口：

- 真实短信服务商、验证码存储、过期校验、错误次数限制和重放保护未实现。
- 生产 token 仍是自定义 HMAC 格式，尚未接入标准 JWT/OIDC、refresh token 或撤销机制。

建议下一步：

- 后续认证增强 PR：接入真实短信/OIDC 与验证码存储。

### 是否有训练历史中心？

状态：部分完成，基础版历史中心已完成。

事实：

- `/sessions/history` 返回当前用户历史训练列表，包含 Session、状态、分数摘要、题目数量、报告入口、继续训练入口和时间信息。
- `/history` 页面已展示当前用户历史训练记录、空状态、查看报告和继续训练入口。
- `/me/reports` 返回最近 50 个 finished sessions。
- PracticePlan 可以利用最近 finished session。
- README 和页面已有最近报告入口。
- `backend/tests/test_training_history.py` 覆盖空历史、按时间倒序、limit/offset、跨用户过滤和 report_id 归属。

缺口：

- `/history` 当前是基础列表，不是完整历史分析工作台。
- 没有按时间、模式、题型、能力维度筛选训练记录。
- 没有完整训练 timeline。
- 没有用户级长期趋势图。

建议下一步：

- PR #33 已基于历史训练补充能力画像 v1。
- 后续历史增强：增加筛选、趋势和训练 timeline。

### 是否有用户能力画像？

状态：部分完成，v1 已完成。

事实：

- `UserTagStat` 记录 tag 维度 attempts 和 avg_score。
- `/me/radar` 暴露能力雷达数据。
- `/me/ability-profile` 返回当前用户总体分、训练次数、完成轮次、累计题量、优势项、薄弱项、标签画像和最近更新时间。
- `/ability` 页面展示当前用户能力画像，支持有数据、空状态和移动端布局。
- `backend/tests/test_ability_profile.py` 覆盖空画像、跨用户隔离、优势/薄弱规则和错题次数对薄弱项的影响。
- PracticePlan 使用弱标签生成推荐。

缺口：

- 画像 v1 仍以 tag 聚合和规则计算为主，缺少时间趋势、置信度、岗位能力模型、表达能力、追问能力。
- 没有画像快照或版本。
- 没有将能力画像和目标岗位进行差距匹配。

建议下一步：

- 后续能力画像增强：增加趋势、画像快照、岗位能力模型和 PracticePlan 的画像引用。

### 是否有长期记忆？

状态：未完成。

事实：

- 当前 `Message` 保存单题对话历史。
- `EvaluationResult` 保存每次评分结构化结果。
- 没有 `agent_memories` 或 memory retrieval 相关模型。

缺口：

- Agent 不会跨 Session 记住用户长期薄弱点、表达习惯、项目经历。
- PracticePlan 只基于错题、弱标签和最近报告，不是长期 Memory。

建议下一步：

- PR #35：Agent Memory v1。新增 memory event、summary、retrieval 设计和最小实现。

### 是否有评分 Rubric 版本化？

状态：部分完成。

事实：

- `EvaluationResult.prompt_version` 默认 `interviewer-v1`。
- `EvaluationResult.model_name` 记录模型名。
- 评分结果包含 score、mastery、strengths、missing_points、action_items。

缺口：

- 没有独立 Rubric 表。
- Rubric 逻辑仍隐含在 prompt 和 fallback 规则里。
- 没有 Rubric 版本、灰度、回放或对比。

建议下一步：

- PR #36：Scoring rubric versioning。引入 Rubric 配置和版本化评估。

### 是否有题库管理后台？

状态：部分完成。

事实：

- `/admin` 前端页面存在。
- `backend/app/api/admin.py` 支持 submissions 列表、审核、JD 生成候选题。
- Admin 路由有 `require_admin`。
- 题库支持 seed、real、UGC、generated 来源。

缺口：

- 没有完整题库列表管理、编辑、禁用、版本、批量操作。
- `QuestionSubmission` 没有 submitter user_id。
- 没有审核审计日志。

建议下一步：

- PR #37：Question bank management v1。

### 是否有权限系统？

状态：部分完成。

事实：

- 有 `require_admin`。
- Admin 权限由 `ADMIN_PHONES` 配置。

缺口：

- 没有角色表、权限表、组织成员表。
- 没有普通用户、教练、审核员、管理员等角色区分。
- 没有资源级权限和租户权限。

建议下一步：

- PR #38：RBAC and organization membership。

### 是否有审计日志？

状态：未完成。

事实：

- 没有 `audit_logs` 模型。
- 没有中间件记录用户操作。
- 没有 admin 审核操作审计。

建议下一步：

- PR #39：Audit log foundation。

### 是否有监控和可观测性？

状态：部分完成，基础版已完成。

事实：

- `backend/app/observability.py` 提供 request_id 中间件、结构化 JSON 日志、HTTPException 统一 `request_id` 响应和 500 兜底响应。
- 每个请求返回 `X-Request-ID`，客户端传入时服务端会规范化并复用。
- `/health` 是轻量存活检查，`/ready` 会执行数据库 `SELECT 1`。
- 核心事件已覆盖登录、Session、answer、report、history、ability profile、practice plan 和 admin 基础访问。
- `backend/tests/test_observability.py` 覆盖 request_id、500 响应、health/ready 和 Authorization token 不进日志。
- `docker-compose.yml` 没有 Prometheus/Grafana。
- `backend/app/main.py` 当前未暴露 metrics endpoint。
- CI 有测试和构建，但没有运行时指标、日志聚合平台和完整 trace propagation。

建议下一步：

- PR #40：Observability metrics and tracing。在 request_id 基础上增加 metrics、trace propagation 和告警设计。

### 是否有生产部署方案？

状态：部分完成。

事实：

- Dockerfile 和 docker-compose 本地可运行。
- CI 会构建前后端镜像。

缺口：

- 没有生产环境部署文档。
- 没有密钥管理、TLS、域名、CORS 生产配置、备份恢复。
- 没有镜像发布 workflow 或环境 promotion。

建议下一步：

- PR #41：Production deployment blueprint。

### 是否有备份和恢复方案？

状态：未完成。

事实：

- `postgres_data` 是 Docker volume。
- 没有备份脚本、恢复脚本、备份测试。

建议下一步：

- PR #42：Backup and recovery runbook。

### 是否有数据隐私设计？

状态：未完成。

事实：

- 用户表存手机号。
- Session、Message、EvaluationResult 保存用户回答和评估内容。
- 当前没有数据导出、删除、脱敏、保留期限设计。

建议下一步：

- PR #43：Privacy and data retention design。

## 缺口总览

| 优先级 | 缺口 | 风险等级 | 为什么重要 | 建议 PR |
| --- | --- | --- | --- | --- |
| P1 | 未接入真实短信和验证码存储 | 高 | 生产环境不能依赖开发验证码，需要可审计的验证码生命周期 | 后续认证增强 |
| P1 | 当前隔离粒度仅为 user_id | 高 | 企业级 SaaS 还需要 organization/tenant 边界 | 后续租户模型 |
| P1 | 训练历史中心仍缺筛选和趋势 | 中 | SaaS 用户需要长期复盘、筛选和趋势分析 | 后续历史增强 |
| P1 | 能力画像 v1 仍缺趋势和岗位模型 | 中 | 个性化训练质量依赖更稳定的长期画像 | 后续画像增强 |
| P1 | 缺少组织/租户模型 | 高 | 企业级 SaaS 需要组织和数据边界 | 后续租户模型 |
| P1 | 缺少 Agent Memory | 中 | Agent 训练系统的差异化核心 | #35 |
| P2 | Rubric 未版本化 | 中 | 评分一致性、回放和解释性不足 | #36 |
| P2 | 题库管理后台不完整 | 中 | 内容运营和质量治理能力不足 | #37 |
| P2 | RBAC 不完整 | 高 | 角色和资源权限无法支持企业场景 | #38 |
| P2 | 审计日志缺失 | 高 | 管理操作和敏感数据访问不可追踪 | #39 |
| P3 | 可观测性仅有基础版 | 中 | 上线后还需要 metrics、trace 和告警 | #40 |
| P3 | 生产部署蓝图缺失 | 中 | 无法形成可复用上线方案 | #41 |
| P3 | 备份恢复缺失 | 高 | 数据丢失风险不可接受 | #42 |
| P3 | 隐私与数据保留缺失 | 高 | 用户回答和手机号属于敏感数据 | #43 |

## 建议修复顺序

1. 后续租户模型：引入组织/租户边界，支撑企业级 SaaS。
2. PR #35：引入 Agent Memory v1。
3. 后续能力画像增强：补趋势、画像快照和岗位能力模型。
4. 后续认证增强：接入真实短信/OIDC、验证码存储、错误次数限制和登录审计。
5. 后续历史增强：补筛选、趋势和完整 timeline。
6. PR #36-#39：补评分、题库、权限、审计。
7. PR #40-#43：补 metrics/tracing、部署、备份、隐私。

## 当前最应该做什么

下一步最应该做组织/租户模型。

原因：

- PR #30 已完成认证生产化基础加固，把开发验证码和生产环境边界拆清楚。
- PR #31 已用测试固化已有 user_id 隔离，投入小、风险收益高，并能保护后续重构。
- PR #32 已完成训练历史中心基础版，让用户能长期回看训练记录和报告沉淀。
- PR #33 已完成能力画像 v1，让历史得分、标签和错题数据进入更稳定的个性化训练基础。
- PR #34 已补生产可观测性地基，让后续多人使用和复杂链路排障有 request_id 与结构化日志基础。
- 后续应补组织/租户边界，这是从单用户 SaaS 走向企业级 SaaS 的关键数据安全前提。
## PR #35 Update: LLM Usage and Cost Metering v1

Status: partially complete.

Completed:

- Added `llm_usage_records`, bound to `user_id`.
- Integrated usage recording into the answer scoring flow for actual LLM call attempts; local rule-based early returns do not create fake usage.
- Successful calls record `status=success`; DeepSeek configuration or response failures that fall back locally record `status=failed` and `error_type`.
- `GET /api/me/usage/summary` is strictly current-user scoped and returns total, current month, by feature, by model and recent records.
- `estimated_cost` uses `pricing_version=llm-pricing-v1-2026-07` and is explicitly an estimate, not a bill.
- The ledger does not store prompt text, model output text, user answer text, tokens, secrets, verification codes or full phone numbers.

Still missing:

- No payment system, plan system, quota deduction, rate limiting or real billing settlement.
- No tenant or organization level usage summary.
- No model quality/cost dashboard.
- No abnormal usage alerting.

Suggested follow-up PRs:

- Organization / tenant model: add tenant scope before tenant-level usage reporting.
- Quota and rate limit v1: build on the ledger after quota policy is designed.
- Model cost dashboard: show cost, failure rate, latency and feature distribution.

## PR #36 Update: Production Config Governance v1

Status: partially complete.

Completed:

- `backend/app/settings.py` now groups app, auth, dev-auth, admin, database, LLM, observability and usage-metering settings.
- Production startup validation rejects unsafe defaults such as default JWT secret, default development verification code, enabled development code, missing database URL, invalid token expiry, missing pricing version, and missing LLM API key when a real provider is enabled.
- `config.loaded` emits only a sanitized configuration summary. Secrets, API keys, verification codes, database passwords and full phone numbers are not logged.
- `.env.example`, Docker Compose development defaults and `docs/configuration.md` now document environment differences and production-required variables.
- Unit tests cover production fail-fast rules and sanitized summary behavior.

Still missing:

- No external configuration center.
- No runtime config reload.
- No tenant-specific configuration.
- No CD release gate that validates production secrets before deployment.

Suggested follow-up PRs:

- Production deployment blueprint: define how production secrets are supplied outside the repository.
- Operational readiness checklist: add release-time config verification steps.
- RBAC and tenant model: add tenant-aware configuration only after tenant boundaries exist.

## PR #37 Update: Release/CD Management v1

Status: partially complete.

Completed:

- Added a manual release candidate workflow with backend tests, frontend checks, optional E2E, Alembic migration gate, Docker Compose config and Docker builds.
- Added release management documentation for local/test/staging/production environment layers.
- Added release evidence template, rollback SOP, hotfix SOP, image tag strategy and migration checklist.
- Existing release image publishing no longer emits mutable `latest` tags.

Still missing:

- No real production deployment.
- No production secrets are configured or required by the release candidate workflow.
- No automatic registry push from the release candidate workflow.
- No backup automation or production migration execution.
- No external CD platform or Kubernetes.

Suggested follow-up PRs:

- Backup and recovery runbook with restore drill.
- Production deployment blueprint for the chosen runtime.
- Registry publishing policy with protected tags and environment approvals.
- Post-release smoke workflow for staging.

## PR #38 Update: Audit Log and Admin Operation Tracking

Status: partially complete.

Completed:

- Added persistent `audit_events` ledger with actor, action, resource, target user, request id, status, reason, request context, sanitized metadata and creation time.
- Added login success and login failure audit events.
- Added admin access and admin denial audit events through the existing admin allowlist guard.
- Added admin-only `GET /api/admin/audit-events` with action, actor, status, limit and offset filters.
- Added sensitive metadata masking for token, secret, verification code, phone, prompt, completion and answer-related fields.
- Added regression tests for login audit, admin audit, non-admin query denial, request id correlation and metadata redaction.

Still missing:

- No full RBAC model.
- No organization or tenant-level audit scope.
- No frontend admin audit console.
- No full report access, data export, privacy request or question review audit coverage.
- No audit retention or archive policy.

Suggested follow-up PRs:

- RBAC and organization membership: replace phone allowlist with roles and resource scopes.
- Audit coverage expansion: add report access, question review, data export and privacy request events.
- Audit retention policy: define retention windows, archive flow and operator access rules.

## PR #39 Update: Rate Limit and Quota v1

Status: partially complete.

Completed:

- Added settings for auth rate limits, answer submission rate limits and LLM token/call quotas.
- Added in-process rate limiter for IP, phone and user/session buckets.
- Added user-scoped LLM quota checks backed by `llm_usage_records`.
- Added 429 responses with `request_id` through the existing observability exception handler.
- Added `quota_exceeded` observability and audit events for LLM quota refusals.
- Added backend tests for login limits, phone limits, answer submit limits, user-isolated LLM quota and sensitive data non-disclosure.

Still missing:

- No Redis or distributed rate-limit store.
- No API gateway limit integration.
- No payment, subscription, billing or commercial plan enforcement.
- No admin quota management UI.
- No tenant-level quota aggregation.

Suggested follow-up PRs:

- Redis-backed rate limiter for multi-instance production.
- Admin quota management and quota override workflow.
- Tenant-level quota model after organization boundaries exist.
- Cost anomaly alerts based on `llm_usage_records`.

## PR #40 Update: RBAC v1

Status: partially complete.

Completed:

- Added `users.role` with default `user`.
- Added `user`, `admin`, and `content_operator` role constants and helper logic.
- Updated admin authorization to allow `role=admin` before checking `ADMIN_PHONES`.
- Kept `ADMIN_PHONES` as a bootstrap/fallback mechanism for local development and early deployments.
- Added audit metadata for admin access source, required role, user role, and RBAC denial reason.
- Added backend tests for default role, role-based admin access, fallback access, content-operator denial, and audit linkage.

Still missing:

- No organization or tenant model.
- No multi-role membership table.
- No resource-level permission matrix.
- No role management API or frontend admin role console.
- `content_operator` is reserved but does not yet unlock content-specific routes.

Suggested follow-up PRs:

- Content operator workflow: allow `content_operator` only for question review routes once that boundary is designed.
- Role management API: admin-only user role update endpoint with audit coverage.
- Organization/tenant membership model after single-user RBAC is stable.
- Resource-scoped permission tests for future report export, question bank management and privacy workflows.

## PR #41 Update: Question Bank Management Backend v1

Status: partially complete.

Completed:

- Reused the existing question bank tables instead of adding a conflicting model.
- Added question lifecycle management metadata: creator, updater, updated time, published time and archived time.
- Added `/api/admin/questions` backend APIs for list, create, update, publish and archive.
- Allowed `admin` and `content_operator` to manage question bank content.
- Kept `content_operator` blocked from admin-only system APIs such as audit event querying.
- Kept ordinary `/api/questions` and session selection scoped to published questions; legacy `active` remains treated as published for existing seed data.
- Added audit events for question creation, update, publishing, archiving and management denial.
- Added backend regression tests for lifecycle, filtering, role access, public visibility and audit coverage.

Still missing:

- No frontend question bank management page.
- No organization or tenant-scoped question ownership.
- No bulk import/review workflow in this PR.
- No question version diffing or rollback.
- No frontend question bank management page integration with rubric selection.

Suggested follow-up PRs:

- Frontend question bank management console using the new backend APIs.
- Question version history and rollback.
- Frontend rubric selection for managed questions.
- Bulk import and review workflow for content operators.

## PR #42 Update: Scoring Rubric Versioning Backend v1

Status: partially complete.

Completed:

- Added `scoring_rubrics` and `scoring_rubric_versions` data models.
- Added optional `questions.default_rubric_version_id` for question-level default scoring standards.
- Added `evaluation_results.rubric_version_id` so new scoring results can be traced to the rubric version actually used.
- Added report question payload `rubric_version_id` so generated reports remain explainable after later rubric changes.
- Added `/api/admin/rubrics` and `/api/admin/rubric-versions/{id}/publish|archive` backend APIs.
- Allowed `admin` and `content_operator` to manage rubrics.
- Kept ordinary users blocked from rubric writes and added `rubric_denied` audit events.
- Added audit events for rubric creation, version creation, publishing and archiving.
- Added `system_default` rubric v1 fallback for questions without a published default rubric version.
- Ensured archived rubric versions are not selected for new scoring.
- Added backend regression tests for RBAC, audit, scoring traceability and historical report stability.

Still missing:

- No frontend rubric management page.
- No rubric diff, replay or rollback workflow.
- No complex scoring-engine rewrite or separate rubric execution engine.
- No gray-release or A/B rollout of rubric versions.
- Existing historical evaluations before PR #42 may have `rubric_version_id = null`.
- No tenant or organization-scoped rubric ownership.

Suggested follow-up PRs:

- Frontend rubric management console for admin/content operators.
- Rubric diff and rollback view.
- Evaluation replay using a selected rubric version.
- Rubric rollout policy once organization/tenant boundaries exist.

## PR #43 Update: Admin Console v1

Status: partially complete.

Completed:

- Added frontend Admin Console routes: `/admin`, `/admin/questions`, and `/admin/rubrics`.
- Added admin/content-operator UI for question list filtering, question creation, editing, publishing and archiving.
- Added admin/content-operator UI for rubric creation, rubric version creation, publishing and archiving.
- Added question default Rubric Version selection using published rubric versions.
- Kept backend RBAC as the source of truth; frontend shows a forbidden state when admin APIs return 403.
- Added Playwright E2E and visual smoke coverage for the admin console.

Still missing:

- No user management or role management UI.
- No organization or tenant model.
- No bulk import/export workflow.
- No rubric diff, rollback, replay or rollout policy UI.
- No billing, plan management or Agent Memory.

Next recommended PRs:

- Question version history and bulk import/export.
- Rubric diff/rollback and evaluation replay.
- Role management API and admin UI after tenant boundaries are designed.

## PR #44 Update: Redis-Backed Rate Limit and Cache Foundation

Status: partially complete.

Completed:

- Added configurable request rate-limit backend: `memory` for local/test and `redis` for staging/production.
- Added Redis limiter counters with TTL for login IP, phone auth and answer-submit buckets.
- Added production fail-fast validation so production cannot run enabled request rate limits on the memory backend.
- Added Redis configuration governance, masked config summary fields and `.env.example` documentation.
- Added `/ready` Redis checks when Redis-backed rate limiting or Redis cache backend is enabled.
- Kept LLM token/call quotas user-scoped through `llm_usage_records`.
- Added backend tests for Redis limiter TTL, 429 headers, production fail-fast, Redis readiness and fallback behavior.

Still missing:

- No API gateway integration.
- No Redis Lua script or token-bucket algorithm; v1 uses simple fixed-window counters.
- No tenant-level quota policy.
- No admin quota management UI.
- No payment, subscription, billing or commercial plan enforcement.
- `CACHE_BACKEND` is only a foundation switch; broad application caching is not implemented.

Suggested follow-up PRs:

- Tenant-level quota model after organization boundaries exist.
- Redis Lua/token-bucket limiter if burst handling becomes a production issue.
- Admin quota override and usage review workflow.
- Cache strategy for low-risk read models only after cache invalidation rules are explicit.

## PR #45 Update: Staging Deployment Foundation

Status: partially complete.

Completed:

- Added `docker-compose.staging.yml` with PostgreSQL, Redis, API and frontend topology.
- Added `.env.staging.example` with placeholder-only staging configuration.
- Added `scripts/staging-smoke.ps1` for health, readiness, request id, frontend and auth-code-path checks.
- Added staging deployment SOP in `docs/staging-deployment.md`.
- Updated release workflow, local CI, release management and release evidence docs with staging compose and smoke evidence.
- Staging config aligns with Redis-backed rate limit/cache settings from PR #44.

Still missing:

- No real staging server is provisioned.
- No registry push or SSH deployment is automated.
- No production deployment is performed.
- No Kubernetes or external CD platform.
- Backup/restore foundation is now covered by PR #46 at script and SOP level; production automation remains future work.

Suggested follow-up PRs:

- Registry publishing workflow for immutable staging release images.
- Staging host provisioning runbook once the runtime target is chosen.
- Post-deploy smoke workflow after a real staging endpoint exists.
- Production offsite backup automation and restore approval workflow.

## PR #46 Update: Backup and Restore Foundation

Status: partially complete.

Completed:

- Added `scripts/backup-postgres.ps1` for local/staging PostgreSQL backups.
- Added `scripts/restore-postgres.ps1` for confirmed local/staging restores.
- Added `scripts/verify-postgres-backup.ps1` for file existence, size, SHA256 and optional table-marker verification.
- Added `docs/backup-and-restore.md` with PostgreSQL scope, Redis backup policy, restore drill, migration pre-backup flow, retention guidance and production requirements.
- Added `docs/backup-evidence-template.md` for release and migration backup evidence.
- Updated release, staging, configuration, README and SaaS architecture docs to require backup evidence before migration rehearsal.

Still missing:

- No production backup is executed by this repository.
- No cloud object storage integration.
- No scheduled backup job.
- No encrypted offsite storage automation.
- No RPO/RTO target enforcement.
- Redis backup remains documented as non-source-of-truth operational data only.

Suggested follow-up PRs:

- Production backup automation after the production runtime is chosen.
- Encrypted offsite backup storage policy and restore approval workflow.
- Periodic restore drill workflow for staging.
- Data retention and privacy deletion policy.

## PR #47 Update: Monitoring Metrics Endpoint and Prometheus Foundation

Status: partially complete.

Completed:

- Added a Prometheus-compatible `/metrics` endpoint with config switches for enablement, path, readiness gauges and production protection.
- Added aggregate HTTP request count, duration and exception metrics with normalized route labels.
- Added training business counters for session creation, answer submission and report generation.
- Added abuse-protection counters for rate-limit and quota refusals.
- Added LLM call, token, estimated-cost and latency metrics linked to the existing LLM usage recording path.
- Added database and Redis readiness gauges updated by `/ready`.
- Added backend regression tests for metrics output, sensitive-label exclusion, disabled endpoint behavior, readiness gauges, rate-limit/quota counters and LLM usage metrics.
- Added metrics documentation and staging smoke coverage for `/metrics`.

Still missing:

- No Grafana dashboard.
- No alert rules.
- No external monitoring SaaS integration.
- No OpenTelemetry tracing.
- No production scrape authentication in this repository; production exposure must be handled by internal networking or gateway controls.

Suggested follow-up PRs:

- Prometheus alert rule pack after a real staging endpoint exists.
- Grafana dashboard templates after metric names stabilize.
- Trace propagation once async worker and LLM spans are designed.
- Production monitoring runbook after deployment target selection.

## PR #48 Update: Agent Memory v1 Backend Foundation

Status: partially complete.

Completed:

- Added `agent_memories` as a relational, user-scoped memory ledger.
- Added current-user APIs for memory list, archive and deterministic refresh.
- Added rule-based generation from report question scores, `WrongBook` recurrence and `UserTagStat` aggregates.
- Added duplicate control by user, memory type and primary tag, with confidence updates instead of unlimited inserts.
- Connected report completion to best-effort memory refresh without failing the answer/report path.
- Connected active weakness and recurring-issue memories to PracticePlan weak-tag recommendations.
- Added audit events for memory creation, update and archive.
- Added aggregate metrics for memories created and refresh status.
- Added tests for generation, duplicate updates, cross-user isolation, archive behavior, PracticePlan exclusion and refresh failure isolation.

Still missing:

- No vector database or embedding memory.
- No RAG memory retrieval.
- No Multi-Agent memory workflow.
- No LLM-based memory extraction or summarization.
- No frontend memory workbench.
- No admin global memory view.
- No tenant or organization-level memory governance.
- No retention or privacy deletion workflow specific to memories.

Suggested follow-up PRs:

- Memory retention and privacy deletion policy after data privacy requirements are finalized.
- LLM-assisted memory extraction with strict redaction and evaluation tests.
- Vector/RAG memory only after tenant/user boundaries and retrieval auditing are designed.
- Frontend current-user memory workbench if user-facing control becomes part of the product experience.

## PR #49 Update: LLM Gateway and Model Router v1

Status: partially complete.

Completed:

- Added backend LLM Gateway and route policy.
- Added feature route configuration for interview scoring, report summary, memory refresh and rubric validation.
- Added primary/fallback provider support and bounded retry configuration.
- Migrated answer scoring to use the gateway by default.
- Kept usage records and metrics aligned with actual provider/model/feature/status attempts.
- Added production config validation for real gateway routes without API keys.
- Added backend tests for route selection, fallback behavior, failed fallback, usage records and sanitized config.

Still missing:

- No model registry database.
- No frontend model management console.
- No tenant-specific model routing.
- No cost-aware routing.
- No canary or A/B routing.
- No circuit breaker or provider health scoring.

Suggested follow-up PRs:

- Model registry and admin route management after the admin governance surface stabilizes.
- Cost-aware routing using `llm_usage_records`.
- Provider health and circuit breaker once staging production traffic exists.
- Tenant-specific model policy after organization/tenant boundaries are introduced.

## PR #50 Update: Async Job Queue Foundation

Status: partially complete.

Completed:

- Added a durable `async_jobs` table scoped by `user_id`.
- Added async job creation, current-user listing and current-user detail APIs.
- Added a lightweight worker entrypoint with memory and Redis queue backend options.
- Added async Agent Memory refresh through `POST /api/me/memories/refresh-async`.
- Added retry state handling with `attempts` and `max_attempts`.
- Added async job audit events and aggregate Prometheus metrics.
- Added local/staging Compose worker services and Redis-backed staging defaults.
- Added tests for user isolation, worker success/failure, payload redaction, Redis backend behavior, metrics and audit.

Still missing:

- No async report generation yet.
- No batch question import job yet.
- No async rubric validation job yet.
- No dead-letter queue.
- No worker concurrency controls.
- No frontend or admin job dashboard.
- No WebSocket push.
- No tenant-level job policy.

Suggested follow-up PRs:

- Move report generation to async job after UX requirements for polling/status are defined.
- Add question import jobs for content-operator workflows.
- Add dead-letter and retry inspection once staging worker traffic exists.
- Add admin/operator job dashboard only after API and audit needs stabilize.
