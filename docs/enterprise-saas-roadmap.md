# Enterprise SaaS Roadmap

本文档定义 Interview Agent 从当前训练闭环产品演进到企业级 SaaS 的实施路线。路线图基于当前代码扫描，不把未完成能力描述为已完成能力。

## Phase 1：用户数据闭环

### 目标

把当前“基础手机号用户 + Bearer token + user_id 过滤”升级为可上线的真实用户数据闭环。

### 关键 PR

1. PR #30：Production-ready auth hardening（已完成基础加固）
2. PR #31：User data isolation regression tests（已完成基础回归测试）
3. PR #32：Training history center v1（已完成基础版）

### 涉及文件

- `backend/app/api/auth.py`
- `backend/app/models.py`
- `backend/alembic/versions/`
- `backend/tests/test_auth.py`
- `backend/tests/test_api_training_loop.py`
- `frontend/lib/api-client.ts`
- `frontend/app/(auth)/login/page.tsx`
- `frontend/app/practice/page.tsx`
- 新增 `frontend/app/history/page.tsx` 或等价历史页面

### 验收标准

- 验证码有过期、错误次数和重放保护。
- 生产环境不能使用固定验证码。
- 用户 A 不能访问用户 B 的 Session、Report、WrongBook、PracticePlan。
- 有训练历史入口，可查看最近训练记录。
- README 和文档准确说明开发模式与生产模式区别。

### 测试要求

- 后端 auth 单元测试。
- 跨用户隔离 API 测试。
- 训练历史 API 测试。
- 前端 E2E 覆盖历史入口和返回今日训练。
- `npm run test:e2e`、本地 CI 和 GitHub CI 全绿。

### 面试讲解价值

- 能说明“我不是只做了页面，而是知道真实 SaaS 首先要解决用户边界和数据隔离”。
- 能展示安全边界如何通过测试防回归。

## Phase 2：训练历史与能力画像

### 目标

让用户看到长期训练轨迹，并让系统具备更稳定的能力画像基础。

### 关键 PR

1. PR #33：Ability profile v1（已完成基础版）
2. PR #44：Training timeline and filters
3. PR #45：Ability trend visualization

### 涉及文件

- `backend/app/models.py`
- `backend/app/api/stats.py`
- `backend/app/api/practice_plan.py`
- `backend/app/schemas.py`
- `frontend/app/practice/page.tsx`
- `frontend/app/report/[id]/page.tsx`
- `frontend/app/history/page.tsx`
- `frontend/app/ability/page.tsx`
- `frontend/lib/stats-api.ts`
- `frontend/lib/ability-profile-api.ts`
- `frontend/lib/types.ts`

### 验收标准

- 能按时间、模式、题型、能力维度查看训练历史。
- 能力画像 v1 不只展示 tag 平均分，还包含训练次数、错题次数、优势项和薄弱项排序；趋势仍属于后续增强。
- PracticePlan 可以引用更稳定的画像数据。
- 页面不伪造不存在的数据。

### 测试要求

- 后端画像计算测试。
- 前端能力画像 E2E 和 visual smoke。
- 前端历史筛选 E2E。
- visual smoke 增加历史页截图。
- API contract 更新。

### 面试讲解价值

- 能讲清楚“训练系统”的核心不是一次评分，而是长期趋势和可行动建议。

## Phase 3：Agent Memory 与个性化训练

### 目标

将用户长期训练结果沉淀为 Agent Memory，让系统能更个性化地推荐训练和追问。

### 关键 PR

1. PR #35：Agent Memory data model
2. PR #46：Memory extraction from reports
3. PR #47：Memory-aware PracticePlan
4. PR #48：Memory retrieval in interview prompt

### 涉及文件

- `backend/app/models.py`
- `backend/alembic/versions/`
- `backend/app/core/interviewer.py`
- `backend/app/core/llm.py`
- `backend/app/api/practice_plan.py`
- `backend/app/api/sessions.py`
- `backend/tests/test_interviewer.py`
- `backend/tests/test_practice_plan.py`

### 验收标准

- 有 `agent_memories` 或等价模型，绑定 `user_id`。
- Memory 来源可追溯到 Session、Report 或 EvaluationResult。
- PracticePlan 推荐可以引用 Memory，但必须可解释。
- Interview prompt 可以读取受控 Memory，不泄露其他用户数据。

### 测试要求

- Memory 生成和去重测试。
- Memory-aware 推荐测试。
- Prompt 输入不包含其他用户数据的隔离测试。
- LLM fallback 下仍能稳定运行。

### 面试讲解价值

- 能展示 Agent 工程能力：Memory、Retrieval、Tool Use、可解释推荐，而不是简单套 LLM。

## Phase 4：题库管理与评分体系

### 目标

把题库和评分从“能用”提升到“可运营、可治理、可回放”。

### 关键 PR

1. PR #36：Scoring rubric versioning
2. PR #37：Question bank management v1
3. PR #49：Question version and status workflow
4. PR #50：Evaluation replay with rubric version

### 涉及文件

- `backend/app/models.py`
- `backend/app/api/admin.py`
- `backend/app/api/questions.py`
- `backend/app/api/sessions.py`
- `backend/app/core/interviewer.py`
- `frontend/app/admin/page.tsx`
- `frontend/lib/admin-api.ts`
- `frontend/lib/types.ts`

### 验收标准

- Rubric 有独立版本和适用范围。
- EvaluationResult 记录 rubric version。
- 管理员可以查看、筛选、编辑、禁用题目。
- 投稿审核有更明确的状态流。
- 评分结果可以按旧 Rubric 回放或对比。

### 测试要求

- Rubric 版本兼容测试。
- Admin 权限测试。
- 题库管理 API 测试。
- 前端 admin E2E 冒烟测试。

### 面试讲解价值

- 能说明 AI 评分系统的“可解释、可版本化、可治理”，这是企业级落地关键点。

## Phase 5：企业级可观测性与安全

### 目标

补齐生产运行所需的可观测性、安全、权限和审计能力。

### 关键 PR

1. PR #34：Production observability foundation（已完成基础版）
2. PR #36：Production config governance（已完成 settings-layer v1）
3. PR #38：RBAC and organization membership
4. PR #39：Audit log foundation
5. PR #40：Observability metrics and tracing
6. PR #43：Privacy and data retention design

### 涉及文件

- `backend/app/models.py`
- `backend/app/main.py`
- `backend/app/observability.py`
- `backend/app/api/auth.py`
- `backend/app/api/admin.py`
- `backend/app/settings.py`
- `backend/tests/test_auth.py`
- `docker-compose.yml`
- `.github/workflows/ci.yml`
- `docs/`

### 验收标准

- 有组织、成员、角色、权限基础模型。
- 管理操作、报告访问、题库审核有审计记录。
- 每个请求有 request id，响应返回 `X-Request-ID`。
- 有结构化请求日志和关键业务事件日志；metrics 和 tracing 属于后续增强。
- 生产环境危险默认配置会 fail fast，启动日志只输出脱敏配置摘要。
- 有数据导出、删除、保留期限和脱敏策略文档。

### 测试要求

- RBAC 权限矩阵测试。
- 审计日志写入测试。
- request id 传播测试。
- 500 错误 request_id 测试。
- 日志敏感信息保护测试。
- production 配置校验和脱敏摘要测试。
- 隐私操作测试或 runbook。

### 面试讲解价值

- 能展示对企业级 SaaS 的理解：权限、审计、观测、隐私不是上线后补丁，而是架构能力。

## Phase 6：部署上线与商业化准备

### 目标

形成可复用的生产部署方案、备份恢复方案和商业化前准备清单。

### 关键 PR

1. PR #41：Production deployment blueprint
2. PR #42：Backup and recovery runbook
3. PR #51：Release image publishing workflow
4. PR #52：Operational readiness checklist

### 涉及文件

- `docker-compose.yml`
- `backend/Dockerfile`
- `frontend/Dockerfile`
- `.github/workflows/`
- `scripts/`
- `docs/deployment/`
- `docs/operations/`

### 验收标准

- 有生产环境变量清单和密钥管理说明。
- 有数据库备份和恢复流程。
- 有镜像发布和版本标记策略。
- 有部署后 smoke test。
- 有回滚策略。
- 有成本、限流和模型调用预算说明。

### 测试要求

- Docker build 持续通过。
- Compose config 持续通过。
- 部署 smoke test 可在 staging 环境运行。
- 备份恢复 runbook 至少可本地演练。

### 面试讲解价值

- 能从“项目能跑”讲到“项目能上线、能运维、能恢复、能商业化试运行”。

## 推荐实施顺序总览

```text
PR #30 认证生产化基础加固（已完成）
PR #31 用户隔离回归测试（已完成）
PR #32 训练历史中心（已完成基础版）
PR #33 能力画像 v1（已完成基础版）
PR #34 生产可观测性地基（已完成基础版）
PR #35 Agent Memory v1
PR #36 Rubric 版本化
PR #37 题库管理 v1
PR #38 RBAC
PR #39 审计日志
PR #40 指标与链路追踪
PR #41 生产部署蓝图
PR #42 备份恢复
PR #43 隐私与数据保留
```

## 下一步建议

最建议立即启动：

1. 组织/租户模型：把当前 `user_id` 隔离升级到 `tenant_id + user_id`。
2. 后续认证增强：真实短信服务商、验证码存储、错误次数限制和登录审计。
3. 后续能力画像增强：趋势、画像快照和岗位能力模型。
4. PR #40：在 request_id 基础上补 metrics、trace propagation 和告警设计。

PR #34 已先补生产可观测性地基，让后续多用户、多租户和 Agent Memory 改造具备基础排障能力。下一步更适合补组织/租户边界。
## PR #35: LLM Usage and Cost Metering v1 (foundation complete)

Goal: prepare the internal LLM usage ledger needed for multi-user operation and later commercialization. The immediate engineering questions are how much was called, what the estimated cost is, where it failed, and which request_id can trace it.

Files involved:

- `backend/app/models.py`
- `backend/alembic/versions/0006_llm_usage_records.py`
- `backend/app/llm_usage.py`
- `backend/app/api/sessions.py`
- `backend/app/api/stats.py`
- `backend/app/schemas.py`
- `backend/tests/test_llm_usage.py`

Acceptance criteria:

- Actual LLM call attempts can be recorded as usage.
- Usage summary is strictly filtered by `current_user.id`.
- `estimated_cost` has a `pricing_version` and is not presented as a bill.
- Failed calls are recorded and can be correlated through `request_id` and structured logs.
- Prompt, completion and answer text are not stored in the ledger.
- Payment, plans, quotas and rate limits are not included.

Interview value:

- Shows that an AI SaaS system needs cost, latency, failure-rate and per-user usage traceability, not only runnable product features.
- Explains why v1 starts with a ledger and summary API before introducing complex billing.

## PR #37 Update: Release/CD Management v1

Status: partially complete.

Completed:

- Added a manual release candidate workflow in `.github/workflows/release.yml`.
- Added `docs/release-management.md` with environment layers, release checklist, migration gate, image tag strategy, rollback SOP and hotfix SOP.
- Added `docs/release-evidence-template.md` for release records.
- Release candidate workflow builds and validates candidate images but does not deploy production and does not push to a registry.
- Existing GHCR image publishing no longer tags images as `latest`; release images use immutable release tags.

Still missing:

- No real production deployment.
- No production secret provisioning flow.
- No automated rollback execution.
- No backup and restore automation.
- No Kubernetes or external CD platform.

## PR #38 Update: Audit Log and Admin Operation Tracking

Status: partially complete.

Completed:

- Added persistent `audit_events` table and Alembic migration.
- Added audit helper with request context extraction, metadata redaction and best-effort write behavior.
- Added security/admin event coverage for login success, login failure, admin access and admin denial.
- Added admin-only audit event query endpoint.
- Added backend tests for audit writes, admin query access control, redaction and request id correlation.

Next roadmap implications:

- Phase 5 now has an audit foundation tied to observability `request_id`.
- RBAC, organization membership and tenant-scoped audit remain separate follow-up work.
- Future audit coverage should include report access, question review, data export and privacy request events.

## PR #39 Update: Rate Limit and Quota v1

Status: partially complete.

Completed:

- Added rate limit and quota settings to the production configuration surface.
- Added in-process request throttling for auth and answer submission hot paths.
- Added user-scoped LLM daily/monthly token and daily call quota checks before scoring.
- Added 429 response coverage with `request_id` correlation.
- Added audit/log coverage for quota denial.

Next roadmap implications:

- The project now has a basic abuse-protection and AI cost guardrail layer.
- Multi-instance production still needs Redis-backed or gateway-backed rate limiting.
- Commercial plans, billing, tenant quotas and admin quota management remain future work.

## PR #40 Update: RBAC v1

Status: partially complete.

Completed:

- Added a single `users.role` field for RBAC v1.
- Added role-aware admin authorization with `user`, `admin`, and `content_operator`.
- Kept `ADMIN_PHONES` as bootstrap/fallback for local and early production setup.
- Connected RBAC decisions to audit events for admin access and denial.
- Added regression tests for role-based admin access, fallback access and content-operator denial.

Next roadmap implications:

- Phase 5 now has a basic RBAC foundation.
- Organization membership, tenant isolation, role management UI/API and resource-level permissions remain future work.
- `content_operator` should be activated only after content review route boundaries and audit rules are explicit.

## PR #41 Update: Question Bank Management Backend v1

Status: partially complete.

Completed:

- Added backend-only question bank management APIs.
- Added question lifecycle fields for managed content.
- Enabled `admin` and `content_operator` to create, update, publish, archive and query questions.
- Preserved ordinary user visibility so only published and legacy active questions are readable/trainable.
- Added audit coverage for question bank management events.

Next roadmap implications:

- Phase 4 now has a backend foundation for content operations.
- The next content-ops step should be a frontend management console or version history, depending on whether operator workflow or governance is the priority.
- Rubric versioning is now covered by PR #42 at backend v1 depth; frontend management, replay and rollout remain separate follow-ups.

## PR #42 Update: Scoring Rubric Versioning Backend v1

Status: partially complete.

Completed:

- Added backend scoring rubric and rubric version models.
- Added admin/content-operator APIs for rubric creation, version creation, publishing and archiving.
- Added rubric audit events and ordinary-user denial audit coverage.
- Connected questions to optional default published rubric versions.
- Connected new evaluation results and generated report question payloads to the actual `rubric_version_id` used during scoring.
- Added system default rubric v1 fallback for questions without a usable published rubric version.
- Added regression tests for RBAC, audit, archived-version exclusion and historical report stability.

Next roadmap implications:

- Phase 4 now has traceable scoring standards for new evaluations.
- Historical evaluations before PR #42 may remain unversioned and should be handled explicitly in future analytics.
- The next scoring-system steps are rubric UI, rubric diff/rollback, evaluation replay and rollout policy.

## PR #43 Update: Admin Console v1

Status: partially complete.

Completed:

- Added frontend routes `/admin`, `/admin/questions`, and `/admin/rubrics`.
- Added a minimal Admin Console overview for content operations.
- Added question bank management UI for list filtering, creation, editing, publishing and archiving.
- Added Rubric management UI for rubric creation, rubric-version creation, publishing and archiving.
- Added forbidden-state handling driven by backend RBAC 403 responses.
- Added admin E2E and visual smoke coverage.

Next roadmap implications:

- Phase 4 now has an operator-facing workflow, not only backend APIs.
- Content governance still needs question version history, bulk import/export and richer review workflow.
- Scoring governance still needs rubric diff, rollback, evaluation replay and rollout policy.
- User management, tenant management, billing and Agent Memory remain separate future phases.

## PR #44 Update: Redis-Backed Rate Limit and Cache Foundation

Status: partially complete.

Completed:

- Added `RATE_LIMIT_BACKEND=memory|redis` and Redis connection governance.
- Kept memory limiter for local/test while requiring Redis-backed rate limiting for production when rate limits are enabled.
- Added Redis counter TTL behavior for auth and answer-submit hot paths.
- Added `/ready` Redis readiness checks when Redis rate limiting or Redis cache backend is enabled.
- Added `CACHE_BACKEND=memory|redis` as a future cache foundation switch.
- Added regression tests for Redis limiter behavior, production fail-fast and Redis readiness.

Next roadmap implications:

- Phase 5 now has a multi-instance abuse-protection foundation.
- The project still needs tenant-level quotas after organization boundaries exist.
- Cache use should be introduced only where invalidation is explicit.
- This PR does not introduce Agent Memory, task queues, payments, subscriptions or billing.

## PR #45 Update: Staging Deployment Foundation

Status: partially complete.

Completed:

- Added a staging Docker Compose topology for PostgreSQL, Redis, API and frontend.
- Added a staging env template with placeholders only and no real secrets.
- Added staging smoke script for `/health`, `/ready`, frontend login and staging auth-code safety.
- Added staging deployment SOP and release evidence updates.
- Added staging compose config validation to release workflow and local CI.

Next roadmap implications:

- Phase 6 now has a release-candidate rehearsal environment design.
- A real staging host, registry publishing and post-deploy smoke automation remain future work.
- Production deployment remains manual-gated and out of scope for this PR.

## PR #46 Update: Backup and Restore Foundation

Status: partially complete.

Completed:

- Added local/staging PostgreSQL backup, restore and verification scripts.
- Added backup and restore SOP plus backup evidence template.
- Integrated migration pre-backup and backup checksum evidence into release/staging docs.
- Documented Redis as rate-limit/cache infrastructure, not the durable source of truth.

Next roadmap implications:

- Phase 6 now has a recoverability foundation for staging rehearsal and migration safety.
- Production still needs encrypted offsite backup storage, scheduled backup policy, restore approval workflow and RPO/RTO targets.
- Backup scripts remain operator-run tools; no production automation or cloud storage was introduced.

## PR #47 Update: Monitoring Metrics Endpoint and Prometheus Foundation

Status: partially complete.

Completed:

- Added Prometheus-compatible `/metrics` for aggregate backend telemetry.
- Added HTTP count, duration and exception metrics.
- Added training event metrics for sessions, answers and reports.
- Added rate-limit and quota refusal metrics.
- Added LLM call, token, estimated-cost and latency metrics.
- Added database and Redis readiness gauges updated by `/ready`.
- Added label-safety rules and tests to prevent high-cardinality or sensitive labels.
- Added metrics docs and staging smoke coverage.

Next roadmap implications:

- Phase 5 now has logs, request ids, audit logs and aggregate metrics.
- Alert rules, dashboards and trace propagation remain future operational maturity work.
- Production metrics access still needs deployment-level protection through internal networking or a gateway.
- No Grafana, external monitoring SaaS or OpenTelemetry tracing was introduced.

## PR #48 Update: Agent Memory v1 Backend Foundation

Status: partially complete.

Completed:

- Added a relational `agent_memories` ledger scoped by `user_id`.
- Added current-user memory APIs for list, archive and refresh.
- Added deterministic memory generation from reports, wrong-book recurrence and tag statistics.
- Added confidence updates so repeated weak or strong tags update existing memories.
- Added best-effort report-completion refresh that does not break the main answer/report flow.
- Added lightweight PracticePlan integration for active weakness and recurring-issue memories.
- Added memory audit events and aggregate Prometheus metrics.
- Added backend regression tests for memory generation, isolation, archive behavior, PracticePlan interaction and failure isolation.

Next roadmap implications:

- Phase 3 now has a safe Agent Memory foundation without vector DB, RAG or Multi-Agent complexity.
- Personalization can now build on training history, ability profile and Agent Memory together.
- LLM extraction, vector retrieval, memory evaluation and memory retention policies remain future PRs.
- Tenant-level memory governance should wait until organization boundaries are designed.

## PR #49 Update: LLM Gateway and Model Router v1

Status: partially complete.

Completed:

- Added backend LLM Gateway and provider abstraction.
- Added feature-based model routing.
- Added primary/fallback provider policy through configuration.
- Added bounded retry/timeout configuration.
- Migrated interview scoring to the gateway.
- Kept usage metering and Prometheus metrics aligned with actual provider/model attempts.
- Added tests for routing, fallback, failure and usage-record behavior.

Next roadmap implications:

- Phase 4/5 now has a model governance foundation without adding a model-management UI.
- Model registry, canary routing, A/B testing and cost-aware routing remain future work.
- Tenant-specific model policy should wait for organization/tenant modeling.
- Gateway telemetry can now support later model quality and cost comparison.

## PR #50 Update: Async Job Queue Foundation

Status: partially complete.

Completed:

- Added user-scoped `async_jobs` as a durable backend job ledger.
- Added memory and Redis queue backends.
- Added `python -m app.worker` as the worker entrypoint.
- Added async Agent Memory refresh as the first low-risk job type.
- Added job status APIs for the current user.
- Added aggregate metrics and audit events for async job lifecycle.
- Added local/staging Compose worker configuration.

Next roadmap implications:

- Phase 3 Agent Memory can now refresh outside synchronous user requests.
- Phase 4 content operations can later add async question import and rubric validation jobs.
- Phase 5 operations now have a worker foundation but still need dead-letter handling, worker concurrency limits and runbook hardening.
- Frontend job status UI remains future work and should wait until more than one user-facing async job exists.

## PR #51 Update: Alerting Rules and Incident Runbook

Completed:

- Added example Prometheus alert rules for API, dependencies, LLM, abuse-protection and async job symptoms.
- Added P0/P1/P2/P3 alert severity guidance.
- Added incident triage and recovery runbook.
- Added incident evidence template.
- Added a lightweight alert-rule file check script.
- Integrated alert and incident checks into staging, release, backup, metrics and observability documentation.

Impact:

- Phase 5 now has a usable operations loop: metrics -> alert symptom -> runbook -> evidence -> recovery -> follow-up.
- Phase 6 release governance now requires checking active P0/P1 incidents and backup evidence before risky migration or rollback decisions.

Still future work:

- Real Prometheus and Alertmanager deployment.
- Grafana dashboards.
- External notification integration.
- Threshold tuning from production data.

## PR #52 Update: Privacy and Data Lifecycle v1

Status: partially complete.

Completed:

- Added current-user data summary, export and deletion APIs.
- Added confirmation-phrase protection for destructive training-data deletion.
- Added export redaction for raw answers, prompts, completions, full phone numbers, tokens, secrets, verification codes and raw model output.
- Added audit events and aggregate metrics for privacy lifecycle operations.
- Documented backup residue, Agent Memory lifecycle, Async Job lifecycle, admin access boundaries and beta privacy checklist.

Next roadmap implications:

- Phase 5 now has a current-user privacy baseline for small real-user trials.
- Phase 6 release and backup governance must treat privacy deletion and backup retention as linked operational evidence.
- Account closure, automated retention jobs, encrypted exports and tenant-level privacy governance remain future work.

## PR #53 Update: Public Beta Readiness Checklist

Status: partially complete.

Completed:

- Added public beta readiness checklist for a small invited trial.
- Added public beta evidence template.
- Added local beta readiness check script.
- Connected beta readiness to release, staging, privacy and incident documentation.
- Defined beta Go / No-Go criteria, forbidden items, operating SOP and exit criteria.

Next roadmap implications:

- Phase 6 now has a practical beta gate before inviting 5 to 10 real users.
- The project can run a controlled trial with manual operations, but it is not a public production launch.
- Production deployment, external alerting, payment, enterprise tenancy, evaluation harness and automated support workflows remain future work.
