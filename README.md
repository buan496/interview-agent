# 大厂面试练习 Agent

一个可运行的 MVP 工程骨架，包含 FastAPI 后端、Next.js 前端、PostgreSQL + pgvector、Redis、LLM 抽象层和单题追问闭环。

> 公开版本说明：内部规划文档未纳入仓库，种子数据中的公司名称已泛化，所有密钥和密码均为本地开发占位值。

## 已实现

- Phase 0 地基: Docker Compose、pgvector/Redis、SQLAlchemy 模型、Alembic 建表迁移、DeepSeek LLM 抽象层、种子题导入脚本。
- Phase 1 核心闭环: `POST /api/sessions` 开始单题、`POST /api/sessions/{id}/answer` SSE 追问/评分、前端筛选页和作答页。
- Phase 2 基础留存: verdict 为 `weak/fail` 时写入错题本，更新用户标签得分。

## 启动

```powershell
Copy-Item .env.example .env
docker compose -p interview-agent up --build
```

打开:

- 前端: http://localhost:3000
- 后端健康检查: http://localhost:8000/health
- API 文档: http://localhost:8000/docs

没有配置 `DEEPSEEK_API_KEY` 时，追问引擎会使用本地 fallback 逻辑，便于先跑通产品闭环。接入真实模型时，在 `.env` 中填入 `DEEPSEEK_API_KEY`。

## 本地后端校验

```powershell
cd backend
$env:PYTHONPATH=(Get-Location).Path
python -m compileall app tests
python -m unittest discover -s tests -p "test_*.py" -v
```

## 目录

```text
backend/app/api        后端接口
backend/app/core       LLM、追问状态机、出题策略
backend/app/ingest     种子题导入、生成/审核预留
backend/alembic        数据库迁移
frontend/app           Next.js 页面
frontend/lib           API 与 SSE 客户端
```

## 后续

设计文档要求的 500 题种子库、模拟面试完整调度、UGC 投稿和语音作答仍属于后续阶段。当前 `questions_seed.jsonl` 是可运行的启动样本，结构已按设计固定。
