from __future__ import annotations

import httpx
from fastapi import APIRouter, File, HTTPException, UploadFile

from app.settings import get_settings


router = APIRouter(prefix="/audio", tags=["audio"])


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)) -> dict[str, str]:
    settings = get_settings()
    if not settings.whisper_api_key:
        raise HTTPException(status_code=503, detail="WHISPER_API_KEY is not configured")
    content = await file.read()
    if not content:
        raise HTTPException(status_code=400, detail="Audio file is empty")
    if len(content) > 25 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio file exceeds 25 MB")

    async with httpx.AsyncClient(timeout=90) as client:
        response = await client.post(
            f"{settings.whisper_base_url.rstrip('/')}/audio/transcriptions",
            headers={"Authorization": f"Bearer {settings.whisper_api_key}"},
            data={"model": settings.whisper_model, "language": "zh"},
            files={"file": (file.filename or "answer.webm", content, file.content_type or "audio/webm")},
        )
    if response.is_error:
        raise HTTPException(status_code=502, detail="Speech transcription provider failed")
    payload = response.json()
    return {"text": str(payload.get("text") or "").strip()}
