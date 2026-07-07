from __future__ import annotations

import contextvars
import json
import logging
import re
import time
from collections.abc import Awaitable, Callable
from typing import Any
from uuid import uuid4

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.settings import Settings


REQUEST_ID_HEADER = "X-Request-ID"

_request_id: contextvars.ContextVar[str | None] = contextvars.ContextVar("request_id", default=None)
_user_id: contextvars.ContextVar[int | None] = contextvars.ContextVar("user_id", default=None)
_request_id_pattern = re.compile(r"[^a-zA-Z0-9_.-]")

logger = logging.getLogger("interview_agent")


def configure_logging(level: str = "INFO") -> None:
    log_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(level=log_level, format="%(message)s")
    logger.setLevel(log_level)


def normalize_request_id(value: str | None) -> str:
    if not value:
        return uuid4().hex
    normalized = _request_id_pattern.sub("-", value.strip())[:64].strip("-_.")
    return normalized or uuid4().hex


def get_request_id() -> str | None:
    return _request_id.get()


def set_user_context(user_id: int | None) -> None:
    _user_id.set(user_id)


def mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    value = str(phone)
    if len(value) <= 4:
        return "****"
    return f"{value[:3]}****{value[-4:]}"


def _json_default(value: Any) -> str:
    return str(value)


def log_event(event_name: str, status: str = "ok", **fields: Any) -> None:
    payload = {
        "event_name": event_name,
        "status": status,
        "request_id": get_request_id(),
        "user_id": _user_id.get(),
        **{key: value for key, value in fields.items() if value is not None},
    }
    logger.info(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=_json_default))


def log_exception(event_name: str, **fields: Any) -> None:
    payload = {
        "event_name": event_name,
        "status": "error",
        "request_id": get_request_id(),
        "user_id": _user_id.get(),
        **{key: value for key, value in fields.items() if value is not None},
    }
    logger.exception(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=_json_default))


class RequestIdMiddleware(BaseHTTPMiddleware):
    def __init__(self, app: FastAPI, request_id_header: str = REQUEST_ID_HEADER) -> None:
        super().__init__(app)
        self.request_id_header = request_id_header or REQUEST_ID_HEADER

    async def dispatch(self, request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        request_id = normalize_request_id(request.headers.get(self.request_id_header))
        request.state.request_id = request_id
        request_token = _request_id.set(request_id)
        user_token = _user_id.set(None)
        started = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            duration_ms = round((time.perf_counter() - started) * 1000, 2)
            log_exception(
                "http_request_exception",
                method=request.method,
                path=request.url.path,
                status_code=500,
                duration_ms=duration_ms,
            )
            response = JSONResponse(
                status_code=500,
                content={"detail": "Internal Server Error", "request_id": request_id},
            )
        duration_ms = round((time.perf_counter() - started) * 1000, 2)
        response.headers[self.request_id_header] = request_id
        if response.status_code >= 500:
            request_status = "error"
        elif response.status_code >= 400:
            request_status = "warning"
        else:
            request_status = "ok"
        request_user_id = getattr(request.state, "user_id", None)
        log_event(
            "http_request",
            status=request_status,
            method=request.method,
            path=request.url.path,
            status_code=response.status_code,
            duration_ms=duration_ms,
            client_ip=request.client.host if request.client else None,
            user_id=request_user_id,
        )
        _request_id.reset(request_token)
        _user_id.reset(user_token)
        return response


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    request_id = get_request_id() or getattr(request.state, "request_id", None) or normalize_request_id(None)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail, "request_id": request_id},
        headers=exc.headers,
    )


def install_observability(app: FastAPI, settings: Settings) -> None:
    configure_logging(getattr(settings, "log_level", "INFO"))
    app.add_middleware(RequestIdMiddleware, request_id_header=getattr(settings, "request_id_header", REQUEST_ID_HEADER))
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.state.service_name = settings.app_name
    app.state.environment = settings.environment
