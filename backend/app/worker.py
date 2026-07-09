from __future__ import annotations

import asyncio

from app.async_jobs import worker_loop
from app.observability import log_event
from app.settings import get_settings


async def main() -> None:
    settings = get_settings()
    settings.validate_production_config()
    log_event(
        "async_worker.start",
        status="success",
        backend=settings.normalized_async_job_backend,
        queue_name=settings.async_job_queue_name,
        poll_seconds=settings.async_job_worker_poll_seconds,
    )
    await worker_loop(settings=settings)


if __name__ == "__main__":
    asyncio.run(main())
