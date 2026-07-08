from __future__ import annotations

from fastapi import FastAPI
from fastapi import Depends
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import admin, admin_questions, audio, auth, practice_plan, questions, sessions, stats, submissions
from app.db import get_db
from app.observability import install_observability, log_event
from app.settings import get_settings


settings = get_settings()
settings.validate_production_config()

app = FastAPI(title=settings.app_name)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
install_observability(app, settings)
log_event("config.loaded", status="success", config=settings.sanitized_config_summary())

app.include_router(auth.router, prefix=settings.api_prefix)
app.include_router(questions.router, prefix=settings.api_prefix)
app.include_router(sessions.router, prefix=settings.api_prefix)
app.include_router(stats.router, prefix=settings.api_prefix)
app.include_router(practice_plan.router, prefix=settings.api_prefix)
app.include_router(admin_questions.router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)
app.include_router(submissions.router, prefix=settings.api_prefix)
app.include_router(audio.router, prefix=settings.api_prefix)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"service": settings.app_name, "status": "ok", "environment": settings.environment}


@app.get("/ready")
async def ready(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    await db.execute(text("SELECT 1"))
    return {"service": settings.app_name, "status": "ready", "environment": settings.environment}
