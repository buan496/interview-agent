# Product Demo Guide

这份文档用于 GitHub 展示、简历项目讲解和面试演示。核心叙事是：Interview Agent 是一个面向 Agent 工程师岗位的 AI 面试训练闭环，而不是普通刷题页面。

## 演示前准备

1. 启动完整服务：

   ```powershell
   Copy-Item .env.example .env
   docker compose -p interview-agent up --build
   ```

2. 打开前端：

   ```text
   http://localhost:3000
   ```

3. 登录说明：

   - 本地演示默认使用 `APP_ENV=development` 和 `AUTH_DEV_CODE_ENABLED=true`，登录接口会返回 `AUTH_DEV_CODE`（默认 `000000`）。
   - 没有配置 `DEEPSEEK_API_KEY` 时，AI 追问和评分使用本地 fallback，适合演示主流程。

4. 视觉截图可通过以下命令刷新：

   ```powershell
   cd frontend
   npm run test:e2e:visual
   ```

## 推荐演示顺序

### 1. 登录页 `/login`

讲解重点：

- 产品定位不是“刷题”，而是“训练闭环”。
- 蓝白品牌体系、Logo、卡片和主 CTA 已统一。
- 登录只是入口，不是本项目的核心展示点。

### 2. 今日训练 `/practice`

讲解重点：

- 登录后的第一屏告诉用户今天该练什么。
- 页面聚合今日训练、薄弱点、错题沉淀和最近报告。
- 主 CTA 能直接进入训练链路，减少用户决策成本。

### 3. 模拟面试 `/mock`

讲解重点：

- 模拟面试是完整 Session，不是单题跳转。
- 可按公司和岗位做筛选，后端真实创建 `mode: "mock"` session。
- 页面清楚说明题目数量、预计时长、追问、报告和错题沉淀。

### 4. 答题 Session `/session/{id}`

讲解重点：

- 用户能看到当前题号、总题数、状态和下一步操作。
- 提交回答后进入 AI 反馈和评分状态。
- 结束后有明确入口进入报告，不会卡在答题页。

### 5. 报告复盘 `/report/{id}`

讲解重点：

- 报告展示综合得分、能力诊断、题目复盘和参考答案。
- 报告不是终点，会给出下一步训练建议。
- 可以自然回到今日训练继续下一轮。

### 6. 错题本 `/wrong-book`

讲解重点：

- 错题本沉淀低分题、失败次数和待复习题。
- 用户可以从错题重新训练，形成长期复盘闭环。
- 这是“训练系统”和“刷题列表”的关键区别。

### 7. 训练历史 `/history`

讲解重点：

- 历史中心只展示当前登录用户自己的训练记录。
- 已完成记录能进入报告复盘，进行中记录能继续回到 Session。
- 这是从“单次训练”走向“长期训练闭环”的基础，但还不是完整趋势分析或导出系统。

### 8. 能力画像 `/ability`

讲解重点：

- 能力画像只展示当前登录用户自己的长期训练表现。
- v1 基于 `UserTagStat`、`Session`、`EvaluationResult` 和 `WrongBook` 做规则聚合，展示总体分、优势项、薄弱项、标签训练次数和错题次数。
- 这不是 Agent Memory，也不是复杂预测模型，而是后续个性化训练和 Memory 的数据地基。

### 9. Admin Console `/admin`

讲解重点：

- Admin Console v1 只面向 `admin` 和 `content_operator`，普通用户访问后台会看到无权限提示，真实权限以后端 RBAC 为准。
- `/admin/questions` 可以创建、编辑、发布和归档题目，并可选择已发布的 Rubric Version 作为题目默认评分标准。
- `/admin/rubrics` 可以创建 Rubric、创建 Version、发布和归档 Version，用于保证后续评分和历史报告可追溯。
- 该版本不做用户管理、租户模型、支付账单或 Agent Memory。

### 10. 工程质量

讲解重点：

- Playwright 覆盖核心路径、导航、mock 创建和视觉冒烟。
- Visual QA 会生成桌面和移动端截图，并检查无横向溢出。
- GitHub Actions 覆盖后端、前端、迁移、Docker 构建、Compose 配置和 Secret Scan。

## 面试官可能会问

### 这个项目和普通刷题网站有什么区别？

回答要点：

- 普通刷题网站通常以题目列表为中心。
- Interview Agent 以训练闭环为中心：今日训练、Session、AI 反馈、报告、错题本、下一轮计划。
- 用户每次训练都会形成可复盘的结果，而不是只完成一次答题。

### LLM 部分如何保证本地可演示？

回答要点：

- 后端有 LLM 抽象层。
- 配置 `DEEPSEEK_API_KEY` 时可以接入真实模型。
- 未配置时走本地 fallback，保证开发、测试和演示稳定。

### 如何避免前端改版破坏主链路？

回答要点：

- PR #25 补强了核心 E2E：practice -> session -> report -> practice。
- PR #27 增加了 visual smoke，覆盖核心页面桌面端和移动端截图。
- CI 中每次 PR 都跑 lint、typecheck、build、E2E 和 Docker 构建。

### 为什么要做视觉 QA，而不是只做 E2E？

回答要点：

- E2E 能保证功能路径可用，但不一定发现布局溢出、移动端导航不可见、CTA 被挤压等问题。
- Visual smoke 不做脆弱像素断言，只保存截图证据并检查无横向溢出。
- 这更适合产品展示型项目持续迭代。

### 后续如何扩展成更强的 Agent 训练系统？

回答要点：

- 增加 Agent Memory，基于长期薄弱点和训练历史做个性化推荐。
- 引入更细粒度评分维度，例如项目表达、Tool Use、RAG、系统设计和追问应对。
- 支持多模型评分对比、报告导出、题库运营和线上部署。

## 演示检查清单

- Docker Compose 能启动。
- `/login` 能登录。
- `/practice` 首页核心 CTA 可见。
- `/mock` 能创建模拟面试。
- `/session/{id}` 能提交回答。
- `/report/{id}` 能回到今日训练。
- `/history` 能进入报告或继续训练。
- `/ability` 能展示能力画像或空状态。
- `/wrong-book` 能进入复盘。
- `/admin` 能展示后台管理入口，普通用户能看到无权限提示。
- `/admin/questions` 能展示题库管理列表和创建表单。
- `/admin/rubrics` 能展示 Rubric 管理列表和版本创建表单。
- `npm run test:e2e` 通过。
- `npm run test:e2e:visual` 能生成截图。
