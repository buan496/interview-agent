# 大厂面试练习 Agent

一个可运行的 AI 模拟面试平台，包含 FastAPI 后端、Next.js 前端、PostgreSQL + pgvector、Redis、LLM 编排、单题追问、模拟面试、报告和题库审核闭环。

> 公开版本说明：内部规划文档未纳入仓库，种子数据中的公司名称已泛化，所有密钥和密码均为本地开发占位值。

## 已实现

- Phase 0 地基：Docker Compose、pgvector/Redis、SQLAlchemy、Alembic、DeepSeek LLM 抽象层、种子题导入。
- Phase 1 核心闭环：手机号验证码登录、单题筛选、SSE 追问/评分、防提示词注入、LLM 未配置时本地 fallback。
- Phase 2 留存闭环：错题本、间隔复习、标签能力统计、6 题模拟面试调度、逐题报告和能力雷达。
- Phase 3 规模化基础：JD 生成候选题、语义去重、UGC 投稿、人工审核入库、ARQ worker、MediaRecorder + Whisper 语音转写。

## 启动

```powershell
Copy-Item .env.example .env
docker compose -p interview-agent up --build
```

打开:

- 前端: http://localhost:3000
- 后端健康检查: `http://localhost:${API_PORT}/health`
- API 文档: `http://localhost:${API_PORT}/docs`

没有配置 `DEEPSEEK_API_KEY` 时，追问引擎会使用本地 fallback 逻辑，便于先跑通产品闭环。接入真实模型时，在 `.env` 中填入 `DEEPSEEK_API_KEY`。

没有配置短信服务时，登录接口会返回开发验证码 `000000`。语音转写默认使用硅基流动的
`FunAudioLLM/SenseVoiceSmall` 模型；没有配置 `WHISPER_API_KEY` 时，文字作答不受影响，
语音转写接口会返回 `503`。

## 本地后端校验

```powershell
cd backend
$env:PYTHONPATH=(Get-Location).Path
python -m compileall app tests
python -m unittest discover -s tests -p "test_*.py" -v
```

前端校验：

```powershell
cd frontend
npm ci
npm run build
npm audit --omit=dev
```

## 目录

```text
backend/app/api        后端接口
backend/app/core       LLM、追问状态机、出题策略
backend/app/ingest     种子题导入、JD 生成与审核预检
backend/alembic        数据库迁移
frontend/app           Next.js 页面
frontend/lib           API 与 SSE 客户端
```

## 主要页面

- `/login` 手机号验证码登录
- `/practice` 单题筛选与练习
- `/mock` 模拟面试设置
- `/session/{id}` 多轮追问、倒计时和语音作答
- `/report/{id}` 综合得分、逐题反馈和能力雷达
- `/wrong-book` 错题复习与一键重练
- `/contribute` 用户投稿
- `/admin` JD 生成题和人工审核

## 内容规模

仓库内置 15 道启动样本和 54 道可追溯公开题目，共 69 道。公开题来自 MIT 或
CC BY 4.0 许可的面试准备项目，来源及改编说明见 `QUESTION_SOURCES.md`。DeepSeek
只用于追问和评分，不用于生成这批题目。

## 许可证

项目代码采用 MIT License。题库中从第三方公开项目整理或改编的内容遵循
`QUESTION_SOURCES.md` 中列出的原始许可证和署名要求。
