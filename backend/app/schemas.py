from __future__ import annotations

from datetime import date
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class CompanyOut(BaseModel):
    id: int
    name: str
    name_en: str | None = None
    region: str
    tier: int | None = None
    logo_url: str | None = None

    model_config = ConfigDict(from_attributes=True)


class PositionOut(BaseModel):
    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class TagOut(BaseModel):
    id: int
    name: str
    category: str | None = None

    model_config = ConfigDict(from_attributes=True)


class MetadataOut(BaseModel):
    companies: list[CompanyOut]
    positions: list[PositionOut]
    tags: list[TagOut]


class QuestionOut(BaseModel):
    id: int
    title: str
    body: str | None = None
    difficulty: int
    qtype: str
    source_type: str
    company: CompanyOut | None = None
    position: PositionOut | None = None
    tags: list[TagOut] = Field(default_factory=list)


class QuestionListOut(BaseModel):
    items: list[QuestionOut]
    total: int


class CreateSessionRequest(BaseModel):
    mode: Literal["single", "mock"] = "single"
    company_id: int | None = None
    position_id: int | None = None
    tag_ids: list[int] = Field(default_factory=list)
    difficulty: int | None = Field(default=None, ge=1, le=5)


class FirstQuestionOut(BaseModel):
    sq_id: int
    title: str
    body: str | None = None
    difficulty: int
    qtype: str
    tags: list[TagOut] = Field(default_factory=list)


class CreateSessionOut(BaseModel):
    session_id: int
    first_question: FirstQuestionOut


class AnswerRequest(BaseModel):
    sq_id: int
    content: str = Field(min_length=1, max_length=8000)


class MessageOut(BaseModel):
    id: int
    role: str
    content: str
    msg_type: str
    eval_json: dict[str, Any] | None = None

    model_config = ConfigDict(from_attributes=True)


class SessionQuestionOut(BaseModel):
    sq_id: int
    question: FirstQuestionOut
    final_score: int | None = None
    mastery: str | None = None
    messages: list[MessageOut]


class SessionDetailOut(BaseModel):
    session_id: int
    mode: str
    status: str
    questions: list[SessionQuestionOut]


class WrongBookOut(BaseModel):
    question_id: int
    title: str
    last_score: int | None = None
    fail_count: int
    next_review: date | None = None
    tags: list[TagOut] = Field(default_factory=list)


class RadarItemOut(BaseModel):
    tag: str
    avg_score: Decimal
    attempts: int

