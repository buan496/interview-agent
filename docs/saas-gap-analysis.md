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

状态：未完成。

事实：

- `docker-compose.yml` 没有 Prometheus/Grafana。
- `backend/app/main.py` 当前未暴露 metrics endpoint。
- CI 有测试和构建，但没有运行时指标、日志聚合、trace id。

建议下一步：

- PR #40：Observability foundation。增加 request id、结构化日志、health/metrics 设计。

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
| P1 | 当前隔离粒度仅为 user_id | 高 | 企业级 SaaS 还需要 organization/tenant 边界 | #34 |
| P1 | 训练历史中心仍缺筛选和趋势 | 中 | SaaS 用户需要长期复盘、筛选和趋势分析 | 后续历史增强 |
| P1 | 能力画像 v1 仍缺趋势和岗位模型 | 中 | 个性化训练质量依赖更稳定的长期画像 | 后续画像增强 |
| P1 | 缺少组织/租户模型 | 高 | 企业级 SaaS 需要组织和数据边界 | #34 |
| P1 | 缺少 Agent Memory | 中 | Agent 训练系统的差异化核心 | #35 |
| P2 | Rubric 未版本化 | 中 | 评分一致性、回放和解释性不足 | #36 |
| P2 | 题库管理后台不完整 | 中 | 内容运营和质量治理能力不足 | #37 |
| P2 | RBAC 不完整 | 高 | 角色和资源权限无法支持企业场景 | #38 |
| P2 | 审计日志缺失 | 高 | 管理操作和敏感数据访问不可追踪 | #39 |
| P3 | 可观测性缺失 | 中 | 上线后排障和稳定性不足 | #40 |
| P3 | 生产部署蓝图缺失 | 中 | 无法形成可复用上线方案 | #41 |
| P3 | 备份恢复缺失 | 高 | 数据丢失风险不可接受 | #42 |
| P3 | 隐私与数据保留缺失 | 高 | 用户回答和手机号属于敏感数据 | #43 |

## 建议修复顺序

1. PR #34：引入组织/租户模型，支撑企业级 SaaS。
2. PR #35：引入 Agent Memory v1。
3. 后续能力画像增强：补趋势、画像快照和岗位能力模型。
4. 后续认证增强：接入真实短信/OIDC、验证码存储、错误次数限制和登录审计。
5. 后续历史增强：补筛选、趋势和完整 timeline。
6. PR #36-#39：补评分、题库、权限、审计。
7. PR #40-#43：补可观测性、部署、备份、隐私。

## 当前最应该做什么

下一步最应该做 PR #34。

原因：

- PR #30 已完成认证生产化基础加固，把开发验证码和生产环境边界拆清楚。
- PR #31 已用测试固化已有 user_id 隔离，投入小、风险收益高，并能保护后续重构。
- PR #32 已完成训练历史中心基础版，让用户能长期回看训练记录和报告沉淀。
- PR #33 已完成能力画像 v1，让历史得分、标签和错题数据进入更稳定的个性化训练基础。
- PR #34 应继续补组织/租户边界，这是从单用户 SaaS 走向企业级 SaaS 的关键数据安全前提。
