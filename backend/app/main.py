from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi import Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.api import admin, admin_questions, admin_rubrics, audio, auth, practice_plan, questions, sessions, stats, submissions
from app.db import get_db
from app.metrics import CONTENT_TYPE_LATEST, metrics_content, set_dependency_ready
from app.observability import install_observability, log_event
from app.redis_client import ping_redis
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
app.include_router(admin_rubrics.router, prefix=settings.api_prefix)
app.include_router(admin_rubrics.version_router, prefix=settings.api_prefix)
app.include_router(admin.router, prefix=settings.api_prefix)
app.include_router(submissions.router, prefix=settings.api_prefix)
app.include_router(audio.router, prefix=settings.api_prefix)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"service": settings.app_name, "status": "ok", "environment": settings.environment}


@app.get("/ready")
async def ready(db: AsyncSession = Depends(get_db)) -> dict[str, str]:
    try:
        await db.execute(text("SELECT 1"))
        if getattr(settings, "metrics_include_ready_gauges", True):
            set_dependency_ready("db", True)
    except Exception:
        if getattr(settings, "metrics_include_ready_gauges", True):
            set_dependency_ready("db", False)
        raise
    redis_status = "skipped"
    if settings.redis_required:
        try:
            redis_status = "ok" if ping_redis(settings) else "failed"
        except Exception as exc:
            redis_status = "failed"
            log_event("readiness.redis", status="error", error_type=exc.__class__.__name__)
        if getattr(settings, "metrics_include_ready_gauges", True):
            set_dependency_ready("redis", redis_status == "ok")
        if redis_status != "ok":
            raise HTTPException(status_code=503, detail={"message": "Redis is not ready", "redis": redis_status})
    elif getattr(settings, "metrics_include_ready_gauges", True):
        set_dependency_ready("redis", True)
    return {"service": settings.app_name, "status": "ready", "environment": settings.environment, "db": "ok", "redis": redis_status}


@app.get(settings.metrics_path, include_in_schema=False)
async def metrics() -> Response:
    if not getattr(settings, "metrics_enabled", True):
        raise HTTPException(status_code=404, detail="Metrics endpoint is disabled")
    if getattr(settings, "is_production", False) and getattr(settings, "metrics_protect_in_production", True):
        raise HTTPException(status_code=403, detail="Metrics endpoint must be protected in production")
    return Response(content=metrics_content(), media_type=CONTENT_TYPE_LATEST)
