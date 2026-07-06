from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_db
from app.models import User
from app.settings import get_settings


router = APIRouter(prefix="/auth", tags=["auth"])


class RequestCodeRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=20)


class LoginRequest(BaseModel):
    phone: str = Field(min_length=6, max_length=20)
    code: str = Field(min_length=4, max_length=8)


def _encode(payload: dict) -> str:
    settings = get_settings()
    raw = base64.urlsafe_b64encode(json.dumps(payload, separators=(",", ":")).encode()).decode().rstrip("=")
    signature = hmac.new(settings.jwt_secret.encode(), raw.encode(), hashlib.sha256).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    return f"{raw}.{encoded_signature}"


def _decode(token: str) -> dict:
    settings = get_settings()
    try:
        raw, encoded_signature = token.split(".", 1)
        expected = hmac.new(settings.jwt_secret.encode(), raw.encode(), hashlib.sha256).digest()
        actual = base64.urlsafe_b64decode(encoded_signature + "=" * (-len(encoded_signature) % 4))
        if not hmac.compare_digest(expected, actual):
            raise ValueError("signature mismatch")
        payload = json.loads(base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)))
        if int(payload.get("exp", 0)) < int(time.time()):
            raise ValueError("token expired")
        return payload
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired token") from exc


def _bearer_token(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(status_code=401, detail="Missing bearer token")
    return authorization.split(" ", 1)[1]


async def _get_or_create_user(db: AsyncSession, phone: str) -> User:
    user = (await db.execute(select(User).where(User.phone == phone))).scalar_one_or_none()
    if user:
        return user
    user = User(phone=phone, nickname=f"用户{phone[-4:]}")
    db.add(user)
    await db.commit()
    await db.refresh(user)
    return user


async def get_current_user(
    authorization: str | None = Header(default=None),
    db: AsyncSession = Depends(get_db),
) -> User:
    payload = _decode(_bearer_token(authorization))
    phone = str(payload.get("sub") or "")
    if not phone:
        raise HTTPException(status_code=401, detail="Invalid token subject")
    return await _get_or_create_user(db, phone)


async def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.phone not in get_settings().admin_phone_set:
        raise HTTPException(status_code=403, detail="Admin privileges required")
    return current_user


@router.post("/request-code")
async def request_code(request: RequestCodeRequest) -> dict[str, str | int]:
    settings = get_settings()
    response: dict[str, str | int] = {"status": "sent", "expires_in": 300}
    if not settings.sms_provider_key:
        response["development_code"] = "000000"
    return response


@router.post("/login")
async def login(request: LoginRequest, db: AsyncSession = Depends(get_db)) -> dict[str, str | int]:
    if request.code != "000000":
        raise HTTPException(status_code=401, detail="Invalid verification code")
    await _get_or_create_user(db, request.phone)
    expires_in = 24 * 60 * 60
    token = _encode({"sub": request.phone, "exp": int(time.time()) + expires_in})
    return {"access_token": token, "token_type": "bearer", "expires_in": expires_in}


@router.get("/me")
async def me(current_user: User = Depends(get_current_user)) -> dict[str, str]:
    return {"phone": str(current_user.phone)}
