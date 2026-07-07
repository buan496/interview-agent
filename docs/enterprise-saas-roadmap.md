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
2. PR #38：RBAC and organization membership
3. PR #39：Audit log foundation
4. PR #40：Observability metrics and tracing
5. PR #43：Privacy and data retention design

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
- 有数据导出、删除、保留期限和脱敏策略文档。

### 测试要求

- RBAC 权限矩阵测试。
- 审计日志写入测试。
- request id 传播测试。
- 500 错误 request_id 测试。
- 日志敏感信息保护测试。
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
