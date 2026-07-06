# AI 面试训练 Agent 系统最终目标设计稿

版本：v1.0
定位：产品主线冻结稿 + 技术架构边界稿 + 防跑偏基准文档

---

## 1. 项目一句话定位

本项目不是普通题库系统，也不是简单的 AI 聊天机器人，而是一个面向大厂 AI 应用开发 / Agent 工程师岗位的智能面试训练 Agent 系统。

它的核心目标是：

让用户通过 AI 模拟面试、结构化追问、能力诊断、错题沉淀和个性化训练计划，持续提升面试通过率。

---

## 2. 项目北极星目标

项目最终要解决一个问题：

用户今天打开系统后，能清楚知道：

1. 我现在最薄弱的能力是什么？
2. 我今天应该练什么？
3. 我练完之后哪里变好了？
4. 我下一步应该怎么继续练？
5. 我是否越来越接近大厂面试要求？

因此，项目的产品主线必须围绕下面这个闭环展开：

```text
登录用户
  ↓
今日训练台
  ↓
推荐练习任务
  ↓
进入单题练习 / 专项训练 / 模拟面试
  ↓
后端维护真实 Session 状态
  ↓
AI 面试官追问与评分
  ↓
生成结构化反馈
  ↓
沉淀错题、薄弱标签、能力画像
  ↓
生成下一轮训练建议
```

项目不能偏离这个闭环。

---

## 3. 明确不做什么

为了防止项目跑偏，以下方向不作为当前阶段核心目标：

1. 不做泛 AI 聊天助手。
2. 不做纯题库管理系统。
3. 不做只展示题目和答案的刷题网站。
4. 不做只追求炫酷 UI 的展示型项目。
5. 不做复杂社区、排行榜、会员体系。
6. 不做求职招聘平台。
7. 不做通用教育平台。
8. 不做算法研究平台。
9. 不做多模型评测平台。
10. 不优先做移动端、小程序、App。

当前核心只做一件事：

构建一个能持续提升用户面试能力的 AI 面试训练闭环。

---

## 4. 目标用户

核心用户：

准备 AI 应用开发、Agent 开发、LLM 工程、后端开发、大厂校招 / 社招面试的人。

用户特点：

1. 有一定编程基础。
2. 需要系统训练八股、项目表达和追问能力。
3. 不知道每天该练什么。
4. 练完题后不知道自己到底哪里差。
5. 面试中容易回答散、回答浅、经不起追问。
6. 需要一个可持续复习和反馈的训练系统。

---

## 5. 核心产品模块

最终系统由 8 个核心模块组成：

```text
1. 用户与权限系统
2. 今日训练台
3. 题库系统
4. 面试 Session 引擎
5. AI 评估与追问引擎
6. 报告与能力画像系统
7. 错题本与复习系统
8. Admin 与异步任务系统
```

---

# 6. 用户与权限系统

## 6.1 设计目标

所有用户数据必须真实隔离。

任何与用户训练相关的数据，都必须绑定真实登录用户，不能再使用 demo 用户。

包括：

```text
Session
Answer
Report
WrongBook
Stats
PracticePlan
Job
```

## 6.2 权限角色

系统至少支持三类角色：

```text
anonymous：未登录用户
user：普通用户
admin：管理员
```

权限规则：

```text
anonymous：
只能访问登录、注册、公开健康检查接口

user：
只能访问自己的训练、报告、错题、统计数据

admin：
可以管理题库、JD、生成任务、用户数据概览
```

## 6.3 后端强制规则

所有私有接口必须依赖：

```text
get_current_user
```

所有后台接口必须依赖：

```text
require_admin
```

禁止在业务接口中使用：

```text
_demo_user
demo_user_id
hardcoded user id
```

## 6.4 验收标准

用户体系合格的标准：

```text
未登录访问私有接口返回 401
普通用户访问 admin 接口返回 403
用户 A 不能看到用户 B 的 Session
用户 A 不能看到用户 B 的 Report
用户 A 不能看到用户 B 的 WrongBook
用户 A 不能看到用户 B 的 Stats
所有创建数据都自动绑定 current_user.id
```

---

# 7. 今日训练台

## 7.1 设计目标

今日训练台是用户进入系统后的主入口。

它不应该只是题库列表，而应该回答用户的问题：

```text
我今天应该练什么？
为什么推荐我练这个？
练完之后能提升什么？
```

## 7.2 页面结构

今日训练台应包含：

```text
1. 继续未完成会话
2. 今日推荐训练
3. 薄弱标签
4. 错题复习入口
5. 模拟面试入口
6. 最近训练记录
7. 能力变化趋势
```

## 7.3 推荐内容来源

推荐训练应该来自：

```text
错题数量
薄弱标签
最近报告
未完成 Session
低分知识点
用户目标岗位
历史训练频率
```

## 7.4 示例推荐

```text
今日建议：
1. 复习 5 道 TCP / Redis 错题
2. 完成 1 次 20 分钟专项模拟
3. 强化“项目落地表达”能力
4. 继续上次未完成的操作系统模拟面试
```

## 7.5 验收标准

今日训练台合格的标准：

```text
用户打开首页后，不需要自己从题库里乱找题
系统能给出明确训练建议
每个建议都有原因
每个建议都能进入具体训练
训练完成后能更新用户能力画像
```

---

# 8. 题库系统

## 8.1 设计目标

题库不是产品主线，只是训练系统的数据来源。

题库系统应该支持：

```text
题目管理
标签管理
难度管理
岗位方向管理
参考答案
考察点
追问问题
评分 Rubric
```

## 8.2 题目核心字段

```text
Question
├── id
├── title
├── content
├── category
├── tags
├── difficulty
├── target_role
├── reference_answer
├── key_points
├── followup_questions
├── scoring_rubric
├── source
├── status
├── created_at
└── updated_at
```

## 8.3 题目类型

支持以下题目类型：

```text
八股基础题
项目经验题
系统设计题
Agent 架构题
RAG 题
LLM 应用题
工程化题
行为面试题
```

## 8.4 题库页面定位

题库页不是主入口，而是辅助入口。

题库页适合：

```text
用户主动搜索题目
管理员维护题目
用户进行自由练习
```

但默认训练路径应该从今日训练台进入。

---

# 9. 面试 Session 引擎

## 9.1 设计目标

Session 是整个项目最核心的技术模型。

后端必须真正维护面试状态，不能只靠前端本地状态模拟。

## 9.2 Session 状态

Session 至少支持以下状态：

```text
created：已创建，未开始
ongoing：进行中
paused：已暂停
expired：已超时
finished：已完成
cancelled：已取消
```

## 9.3 Session 状态流转

```text
created
  ↓ start
ongoing
  ↓ finish
finished

ongoing
  ↓ timeout
expired

ongoing
  ↓ cancel
cancelled

ongoing
  ↓ pause
paused
  ↓ resume
ongoing
```

## 9.4 Session 核心字段

```text
Session
├── id
├── user_id
├── mode
├── status
├── started_at
├── deadline_at
├── finished_at
├── expired_at
├── current_question_id
├── current_question_index
├── total_questions
├── max_followups
├── current_followups
├── end_reason
├── created_at
└── updated_at
```

## 9.5 SessionQuestion 核心字段

每道题在 Session 中应该有独立状态：

```text
SessionQuestion
├── id
├── session_id
├── question_id
├── status
├── started_at
├── submitted_at
├── scored_at
├── answer_text
├── score
├── verdict
├── followup_count
├── strengths
├── missing_points
├── expression_issues
├── action_items
└── recommended_questions
```

## 9.6 计时规则

倒计时必须以后端为准。

前端不能自己决定 Session 是否过期。

后端需要返回：

```text
server_now
started_at
deadline_at
remaining_seconds
status
```

提交答案时，后端必须再次校验：

```text
如果当前时间超过 deadline_at，则拒绝提交并将 Session 标记为 expired
```

## 9.7 验收标准

Session 引擎合格的标准：

```text
刷新页面不会重置倒计时
过期 Session 不能继续提交
finished Session 不能重复提交
cancelled Session 不能继续答题
后端能知道当前第几题
后端能知道每题是否已评分
后端能知道追问次数
后端能记录结束原因
```

---

# 10. 面试工作台

## 10.1 设计目标

会话页不是普通聊天页，而是面试工作台。

用户应该清楚知道：

```text
当前第几题
本题考察什么
我应该怎么回答
AI 是否在追问
当前追问到第几轮
什么时候进入下一题
最终评分是什么
下一步应该做什么
```

## 10.2 页面布局

推荐布局：

```text
顶部：
Session 状态、剩余时间、当前进度、模式

左侧：
题目内容、本题考察点、答题目标、参考结构、追问进度

中间：
用户答题区、语音输入、文本输入、提交按钮

右侧：
AI 面试官反馈、追问问题、评分结果、缺失知识点、下一步操作
```

## 10.3 每题阶段

每道题应具备清晰阶段：

```text
reading：阅读题目
answering：用户作答
followup：AI 追问
scoring：评分中
review：查看反馈
next_ready：可以进入下一题
```

## 10.4 验收标准

面试工作台合格的标准：

```text
用户不会感觉自己在随机聊天
用户能明确知道本轮目标
用户能看到追问进度
用户能看到当前阶段
用户能看到明确下一步按钮
用户能理解 AI 给出的评分和建议
```

---

# 11. AI 评估与追问引擎

## 11.1 设计目标

LLM 不只是生成文本，而是作为面试评估 Agent。

它应该完成：

```text
理解题目
分析用户回答
判断是否需要追问
生成追问问题
结构化评分
提取缺失知识点
生成下一步训练建议
```

## 11.2 LLM 输出必须结构化

评分结果必须使用 JSON 结构，不允许只保存一段自然语言。

单题评估结构：

```text
EvaluationResult
├── score
├── level
├── verdict
├── strengths
├── missing_points
├── expression_issues
├── followup_failures
├── action_items
├── recommended_questions
├── raw_model_output
├── model_name
├── prompt_version
└── created_at
```

## 11.3 评分维度

至少包含：

```text
知识准确性
回答结构
深度
项目落地能力
表达清晰度
追问抗压能力
```

## 11.4 追问策略

AI 追问不应该无限进行。

每题需要限制：

```text
最大追问次数
追问目标
追问结束条件
最终评分条件
```

追问应围绕：

```text
核心概念缺失
边界情况
项目应用
性能问题
故障排查
大厂真实场景
```

## 11.5 验收标准

AI 评估合格的标准：

```text
每次评分都有结构化 JSON
评分失败时有兜底处理
JSON 解析失败不会导致系统崩溃
每题能沉淀 missing_points
每题能沉淀 action_items
每题能推荐后续练习
每次调用记录 model_name 和 prompt_version
```

---

# 12. 报告与能力画像系统

## 12.1 设计目标

报告不是简单分数页，而是用户复习路线的依据。

报告必须回答：

```text
我哪里强？
我哪里弱？
我为什么丢分？
我下一步应该练什么？
```

## 12.2 报告层级

报告分三层：

```text
整体报告
能力维度报告
逐题诊断报告
```

## 12.3 整体报告结构

```text
Report
├── id
├── user_id
├── session_id
├── overall_score
├── summary
├── ability_scores
├── weak_tags
├── strong_tags
├── next_plan
├── created_at
└── updated_at
```

## 12.4 能力维度

至少包含：

```text
基础知识
回答结构
技术深度
工程落地
系统设计
Agent 理解
表达能力
追问抗压
```

## 12.5 逐题诊断

每题必须展示：

```text
题目
用户回答
AI 追问
最终评分
优点
缺失知识点
表达问题
追问失败原因
行动建议
推荐复习题
```

## 12.6 验收标准

报告系统合格的标准：

```text
报告不是只有雷达图
报告能指出具体知识缺口
报告能指出表达问题
报告能生成下一步训练建议
报告能沉淀到错题本和能力画像
用户看完报告知道下一步练什么
```

---

# 13. 错题本与复习系统

## 13.1 设计目标

错题本不是简单收藏，而是复习闭环的一部分。

错题来源：

```text
低分题目
追问失败题目
用户手动加入
系统自动判定薄弱题
```

## 13.2 错题字段

```text
WrongBookItem
├── id
├── user_id
├── question_id
├── session_id
├── reason
├── weak_points
├── last_score
├── review_count
├── mastered
├── next_review_at
├── created_at
└── updated_at
```

## 13.3 复习策略

系统应根据错题生成复习任务：

```text
今日错题复习
薄弱标签复习
低分题重练
追问失败题重练
已掌握题移出错题本
```

## 13.4 验收标准

错题本合格的标准：

```text
错题属于真实用户
错题有加入原因
错题能看到薄弱点
错题能重新练习
错题能标记掌握
错题能参与今日推荐
```

---

# 14. PracticePlan 训练计划

## 14.1 设计目标

PracticePlan 是防止产品变成散乱题库的关键模型。

它负责把用户数据转成训练任务。

## 14.2 PracticePlan 字段

```text
PracticePlan
├── id
├── user_id
├── date
├── recommended_tasks
├── weak_tags
├── target_abilities
├── generated_reason
├── completed
├── created_at
└── updated_at
```

## 14.3 推荐任务类型

```text
wrong_book_review：错题复习
weak_tag_training：薄弱标签训练
mock_interview：模拟面试
single_question：单题练习
project_expression：项目表达训练
system_design：系统设计训练
```

## 14.4 验收标准

训练计划合格的标准：

```text
系统能基于历史表现推荐任务
推荐任务有理由
推荐任务能直接进入 Session
完成任务后能更新计划状态
计划能影响下一次推荐
```

---

# 15. Admin 与异步任务系统

## 15.1 设计目标

后台主要服务题库建设、JD 生成、批量生成、任务管理。

后台功能不能影响普通用户训练主线。

## 15.2 Admin 功能

```text
题库管理
标签管理
JD 管理
批量题目生成
异步任务队列
任务失败重试
系统数据概览
```

## 15.3 长任务必须异步化

以下任务不应该使用同步 API：

```text
JD 生成
批量题目生成
长报告生成
批量评测
语音转写
Agent 多步执行
```

## 15.4 Job 模型

```text
Job
├── id
├── type
├── status
├── input_payload
├── output_payload
├── error_message
├── retry_count
├── created_by
├── created_at
├── started_at
└── finished_at
```

Job 状态：

```text
queued
running
succeeded
failed
cancelled
```

## 15.5 验收标准

异步任务系统合格的标准：

```text
长任务不会阻塞前端
前端能查看任务状态
失败任务有错误信息
管理员能重试失败任务
所有任务绑定创建人
普通用户不能访问 admin job 页面
```

---

# 16. 前端架构边界

## 16.1 统一 API Client

页面中禁止散落裸 fetch。

所有请求必须通过统一 API Client：

```text
lib/api.ts
lib/session-api.ts
lib/report-api.ts
lib/wrong-book-api.ts
lib/admin-api.ts
```

统一处理：

```text
Authorization
401
403
500
loading
error
baseURL
JSON 解析
```

## 16.2 组件体系

基础组件：

```text
PageShell
PageHeader
SectionTitle
Button
Badge
ScoreBadge
StatusBadge
EmptyState
ErrorState
LoadingState
FormField
DataTable
ConfirmDialog
ProgressBar
```

业务组件：

```text
TrainingCard
WeakTagCard
SessionProgress
QuestionPanel
AnswerEditor
InterviewFeedbackPanel
ReportSummary
WrongBookItemCard
JobStatusCard
```

## 16.3 页面职责

页面只负责组合组件和调用业务 API。

页面不应该承担：

```text
复杂 fetch 逻辑
鉴权逻辑
错误处理逻辑
复杂状态机逻辑
重复 UI 拼装
```

---

# 17. 后端架构边界

后端推荐模块划分：

```text
auth
users
questions
sessions
evaluations
reports
wrong_book
practice_plan
admin
jobs
observability
```

核心服务层：

```text
SessionService
EvaluationService
ReportService
WrongBookService
PracticePlanService
JobService
```

Controller / API 层只做：

```text
参数校验
权限校验
调用 service
返回响应
```

业务逻辑不要堆在 route 文件里。

---

# 18. 数据模型总览

最终核心数据关系：

```text
User
  ├── PracticePlan
  ├── Session
  │     ├── SessionQuestion
  │     │     └── EvaluationResult
  │     └── Report
  ├── WrongBookItem
  ├── UserStats
  └── Job

Question
  ├── tags
  ├── key_points
  ├── followup_questions
  └── scoring_rubric
```

核心原则：

```text
用户私有数据必须带 user_id
Session 是训练过程核心
EvaluationResult 是 AI 输出核心
Report 是训练结果核心
PracticePlan 是下一步推荐核心
WrongBookItem 是复习闭环核心
Job 是后台异步任务核心
```

---

# 19. 工程化要求

## 19.1 CI

必须具备基础 CI：

```text
后端测试
前端构建
Lint
Docker build 验证
密钥泄露检查
```

## 19.2 数据库迁移

必须使用 migration 管理表结构。

推荐：

```text
Alembic
```

所有 schema 变更必须有迁移文件。

## 19.3 配置管理

禁止硬编码密钥。

配置来源：

```text
.env
环境变量
GitHub Secrets
Docker Compose env_file
生产服务器 Secret
```

## 19.4 日志

关键日志必须包含：

```text
request_id
user_id
session_id
endpoint
latency
status_code
error_message
model_name
prompt_version
```

禁止记录：

```text
完整 API Key
完整数据库密码
敏感用户隐私
```

## 19.5 监控

至少应监控：

```text
API 错误率
接口延迟
LLM 调用失败率
JSON 解析失败率
Job 失败数
队列长度
数据库连接
CPU / 内存 / 磁盘
```

---

# 20. 阶段路线图

## Phase 1：地基重构

目标：从 demo 系统变成真实多用户系统。

任务：

```text
实现 get_current_user
实现 require_admin
移除 _demo_user
所有用户数据绑定 user_id
统一前端 API Client
禁止裸 fetch
admin 加权限保护
```

验收：

```text
用户数据完全隔离
未登录返回 401
普通用户访问 admin 返回 403
前端请求统一携带 token
```

---

## Phase 2：Session 状态机

目标：让模拟面试从前端表演变成后端真实状态。

任务：

```text
扩展 Session 状态
增加 deadline_at
增加 remaining_seconds
增加 SessionQuestion
实现提交约束
实现过期处理
实现完成 / 取消 / 暂停
```

验收：

```text
刷新不重置时间
过期不能提交
已完成不能重复提交
后端能判断当前题和当前阶段
```

---

## Phase 3：面试工作台

目标：让用户体验像真实面试训练，而不是普通聊天。

任务：

```text
重做 session 页面
展示题目目标
展示追问进度
展示当前阶段
展示评分结果
提供下一步操作
```

验收：

```text
用户知道现在该干什么
用户知道 AI 为什么追问
用户知道什么时候进入下一题
```

---

## Phase 4：结构化报告

目标：让报告能指导复习。

任务：

```text
LLM 输出结构化 JSON
沉淀 strengths
沉淀 missing_points
沉淀 expression_issues
沉淀 action_items
生成 recommended_questions
报告页重做
```

验收：

```text
报告不只是分数
报告能指出具体问题
报告能推荐下一步训练
```

---

## Phase 5：今日训练台与 PracticePlan

目标：建立训练闭环。

任务：

```text
新增 PracticePlan
基于错题和弱标签生成今日推荐
首页改成今日训练台
支持继续未完成 Session
支持错题复习
支持薄弱标签训练
```

验收：

```text
用户打开首页知道今天练什么
推荐任务能进入具体 Session
训练结果能影响下一次推荐
```

---

## Phase 6：Admin 与异步 Job

目标：后台任务工程化。

任务：

```text
JD 生成异步化
批量题目生成异步化
新增 Job 表
新增 Job 状态页
支持失败重试
```

验收：

```text
长任务不阻塞前端
任务状态可见
失败原因可追踪
```

---

## Phase 7：工程化增强

目标：让项目具备生产级雏形。

任务：

```text
CI
Docker Compose
Alembic migration
结构化日志
Prometheus metrics
基础告警
部署文档
回滚 SOP
```

验收：

```text
新代码有质量门禁
服务可一键部署
问题可观测
失败可回滚
```

---

# 21. 防跑偏决策清单

以后任何新增功能，都必须回答以下问题：

```text
1. 这个功能是否服务“面试训练闭环”？
2. 它能提升用户面试能力吗？
3. 它会沉淀到 Session / Report / WrongBook / PracticePlan 中吗？
4. 它是否破坏用户数据隔离？
5. 它是否绕过统一 API Client？
6. 它是否绕过后端鉴权？
7. 它是否只是 UI 炫技？
8. 它是否只是题库堆叠？
9. 它是否会增加主线复杂度？
10. 它是否能被测试和验收？
```

如果一个功能不能明确回答前 3 个问题，默认不做。

---

# 22. 大厂面试包装方向

最终项目可以包装为：

一个面向 AI 应用开发岗位的智能面试训练 Agent 系统，支持真实用户体系、模拟面试状态机、AI 追问、结构化评分、错题沉淀、能力画像、个性化训练计划和异步后台任务。

核心亮点：

```text
1. 真实多用户数据隔离
2. 后端 Session 状态机
3. LLM 结构化评估
4. AI 追问策略
5. 错题与能力画像沉淀
6. 个性化 PracticePlan 推荐
7. 异步任务队列
8. Admin 题库与 JD 生成
9. 前后端统一鉴权
10. CI / Docker / Migration / Observability 工程化能力
```

面试时重点讲：

```text
我不是简单调用大模型，而是把 LLM 放进一个可控的训练工作流里。

系统通过 Session 状态机约束面试流程，通过结构化 EvaluationResult 沉淀能力数据，通过 WrongBook 和 PracticePlan 形成复习闭环，最终让用户的训练行为、AI 反馈和下一步推荐形成闭环。
```

---

# 23. 最终验收标准

项目达到最终目标时，应该满足：

```text
用户登录后只能看到自己的数据
用户打开首页知道今天练什么
用户可以进入真实受控的模拟面试
后端维护 Session 状态和倒计时
AI 能进行有限追问
AI 能输出结构化评分
报告能指出具体问题
错题能自动沉淀
系统能推荐下一步训练
Admin 有权限保护
长任务走异步 Job
前端没有散落裸 fetch
后端没有 demo 用户
核心逻辑有测试
项目可以 Docker Compose 部署
CI 能阻止明显坏代码合并
```

只有满足这些条件，这个项目才算从“AI Demo”升级为“AI Agent 产品级项目”。

---

# 24. 最重要的项目纪律

本项目后续所有开发都必须遵守三条纪律：

第一，任何功能必须服务训练闭环。

第二，任何用户数据必须绑定真实用户。

第三，任何面试流程状态必须以后端 Session 引擎为准。

只要守住这三条，项目就不会跑偏。
