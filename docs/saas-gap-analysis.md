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
| 登录入口 | 部分完成 | `backend/app/api/auth.py` 有手机号验证码接口和 Bearer token；`frontend/app/(auth)/login/page.tsx` 有登录页 |
| 当前用户解析 | 已完成基础版 | `get_current_user` 解析 token subject，并读取或创建 `User` |
| Admin 保护 | 部分完成 | `require_admin` 基于 `ADMIN_PHONES`；`backend/app/api/admin.py` 对整个 router 使用依赖 |
| Session 绑定用户 | 已完成基础版 | `Session.user_id` 非空；创建、读取、提交、报告按 `current_user.id` 过滤 |
| Report 绑定用户 | 已完成基础版 | Report 存在 `Session.report`，读取报告时按 `Session.user_id` 过滤 |
| WrongBook 绑定用户 | 已完成基础版 | `WrongBook` 主键为 `user_id + question_id`；查询按当前用户过滤 |
| 能力统计 | 部分完成 | `UserTagStat` 按 `user_id + tag_id` 记录平均分和次数 |
| 今日计划 | 部分完成 | `PracticePlan` 按 `user_id + plan_date` 唯一；可基于错题、弱标签、报告行动项生成任务 |
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
- 本地开发验证码固定为 `000000`，`request-code` 在没有短信服务时返回 `development_code`。

缺口：

- 没有真实短信服务集成状态记录。
- 没有验证码发送记录、验证码过期校验、错误次数限制。
- 没有 refresh token、设备管理、退出登录服务端撤销。
- token 是自定义 HMAC 格式，不是标准 JWT/OIDC 实现。

建议下一步：

- PR #30：Production-ready auth hardening。引入验证码存储、过期、错误次数、rate limit、标准 JWT 或认证服务集成。

### 后端数据是否按 user_id 隔离？

状态：大部分训练数据已完成基础隔离。

事实：

- `Session.user_id` 创建时写入 `current_user.id`。
- `get_session`、`get_report`、`answer` 查询均要求 `Session.user_id == current_user.id`。
- `_answer_stream` 二次校验 `sq.session.user_id != user_id` 时拒绝。
- `WrongBook`、`UserTagStat`、`PracticePlan` 都包含 `user_id`。
- `stats.py` 中 wrong-book、radar、reports 均按当前用户过滤。

缺口：

- 题库是全局共享，没有 tenant/organization 维度。
- 投稿 `QuestionSubmission` 没有绑定提交用户 id，仅有 `submitter_name`。
- 没有系统级测试覆盖“用户 A 不能访问用户 B 的 Session/Report/WrongBook”。
- 没有租户级隔离。

建议下一步：

- PR #31：User data isolation regression tests。先补跨用户访问测试。
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

- PR #32：Training history and report model boundary。增加训练历史/报告边界文档或独立 Report 表设计。

### 是否存在 demo user、mock user、硬编码用户？

状态：未发现后端 demo user 数据路径；存在开发验证码和 E2E mock 数据。

事实：

- 后端 `auth.py` 根据手机号创建真实 `User` 行。
- 没有 `_demo_user` 函数。
- E2E 使用 `frontend/tests/e2e/helpers/core-fixtures.ts` mock API 响应，这是测试层数据。
- `request-code` 无短信配置时返回 `development_code: "000000"`。
- `login` 仅接受 `code == "000000"`。

缺口：

- 固定验证码只适合开发，不能用于生产。
- 没有环境保护来防止生产误用开发验证码。

建议下一步：

- PR #30：Production-ready auth hardening。

### 是否有训练历史中心？

状态：部分完成。

事实：

- `/me/reports` 返回最近 50 个 finished sessions。
- PracticePlan 可以利用最近 finished session。
- README 和页面已有最近报告入口。

缺口：

- 没有独立 `/history` 页面。
- 没有按时间、模式、题型、能力维度筛选训练记录。
- 没有完整训练 timeline。
- 没有用户级长期趋势图。

建议下一步：

- PR #32：Training history center。新增历史 API 和页面。

### 是否有用户能力画像？

状态：部分完成。

事实：

- `UserTagStat` 记录 tag 维度 attempts 和 avg_score。
- `/me/radar` 暴露能力雷达数据。
- PracticePlan 使用弱标签生成推荐。

缺口：

- 画像维度仅 tag 平均分，缺少时间趋势、置信度、岗位能力模型、表达能力、追问能力。
- 没有画像快照或版本。
- 没有将能力画像和目标岗位进行差距匹配。

建议下一步：

- PR #33：Ability profile v1。扩展能力画像模型和可视化。

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
| P0 | 生产认证仍是开发验证码 | 高 | 直接阻塞真实用户上线 | #30 |
| P0 | 缺少跨用户隔离回归测试 | 高 | 当前有隔离逻辑，但需要测试防回归 | #31 |
| P1 | 缺少训练历史中心 | 中 | SaaS 用户需要长期复盘和趋势 | #32 |
| P1 | 能力画像过粗 | 中 | 个性化训练质量依赖画像质量 | #33 |
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

1. PR #30：先修认证，把本地开发验证码和生产认证边界拆清楚。
2. PR #31：补用户数据隔离回归测试，防止后续重构破坏数据边界。
3. PR #32：做训练历史中心，让 SaaS 用户能查看长期训练记录。
4. PR #33：扩展能力画像，为 Agent Memory 和个性化训练打基础。
5. PR #34：引入组织/租户模型，支撑企业级 SaaS。
6. PR #35：引入 Agent Memory v1。
7. PR #36-#39：补评分、题库、权限、审计。
8. PR #40-#43：补可观测性、部署、备份、隐私。

## 当前最应该做什么

下一步最应该做 PR #30 和 PR #31。

原因：

- PR #30 解决真实用户体系生产化问题，是 SaaS 上线前的基础门禁。
- PR #31 用测试固化已有 user_id 隔离，投入小、风险收益高，并能保护后续重构。
