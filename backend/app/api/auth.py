from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel


router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    phone: str = "demo"
    code: str = "000000"


@router.post("/login")
async def login(_: LoginRequest) -> dict[str, str]:
    return {"access_token": "demo-token", "token_type": "bearer"}

