from __future__ import annotations

from arq.connections import RedisSettings

from app.ingest.generator import generate_from_jd
from app.settings import get_settings


async def generate_questions_job(
    _ctx,
    jd_text: str,
    company: str,
    position: str,
    count: int = 5,
) -> list[dict]:
    items = await generate_from_jd(jd_text, company, position, count)
    return [item.__dict__ for item in items]


class WorkerSettings:
    functions = [generate_questions_job]
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url)
