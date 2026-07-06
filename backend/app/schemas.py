from __future__ import annotations

from datetime import date, datetime
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
    source_note: str | None = None
    company: CompanyOut | None = None
    position: PositionOut | None = None
    tags: list[TagOut] = Field(default_factory=list)


class QuestionListOut(BaseModel):
    items: list[QuestionOut]
    total: int


class CreateSessionRequest(BaseModel):
    mode: Literal["single", "mock"] = "single"
    question_id: int | None = None
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
    status: str
    server_now: datetime
    deadline_at: datetime | None = None
    remaining_seconds: int | None = None


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
    status: str
    started_at: datetime | None = None
    submitted_at: datetime | None = None
    scored_at: datetime | None = None
    followup_count: int = 0
    final_score: int | None = None
    mastery: str | None = None
    messages: list[MessageOut]


class SessionDetailOut(BaseModel):
    session_id: int
    mode: str
    status: str
    server_now: datetime
    started_at: datetime | None = None
    deadline_at: datetime | None = None
    remaining_seconds: int | None = None
    current_question_index: int = 1
    total_questions: int = 1
    max_followups: int = 3
    current_followups: int = 0
    end_reason: str | None = None
    questions: list[SessionQuestionOut]


class ReportQuestionOut(BaseModel):
    sq_id: int
    title: str
    qtype: str
    difficulty: int
    score: int
    mastery: str
    feedback: str
    ideal_answer: str
    tags: list[TagOut] = Field(default_factory=list)


class SessionReportOut(BaseModel):
    session_id: int
    mode: str
    status: str
    overall_score: int
    summary: str
    started_at: datetime
    ended_at: datetime | None = None
    radar: list["RadarItemOut"] = Field(default_factory=list)
    questions: list[ReportQuestionOut] = Field(default_factory=list)


class ReportListItemOut(BaseModel):
    session_id: int
    mode: str
    status: str
    overall_score: int
    started_at: datetime
    ended_at: datetime | None = None


class PracticePlanTaskOut(BaseModel):
    id: str
    type: Literal[
        "wrong_book_review",
        "resume_session",
        "weak_tag_training",
        "mock_interview",
        "single_question",
        "project_expression",
        "system_design",
    ]
    title: str
    reason: str
    outcome: str
    action_label: str
    entrypoint: Literal["create_session", "open_page"]
    payload: dict[str, Any] = Field(default_factory=dict)


class PracticePlanOut(BaseModel):
    id: int
    date: date
    recommended_tasks: list[PracticePlanTaskOut]
    weak_tags: list[dict[str, Any]] = Field(default_factory=list)
    target_abilities: list[str] = Field(default_factory=list)
    generated_reason: str
    completed: bool
    created_at: datetime
    updated_at: datetime | None = None


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


class SubmissionCreate(BaseModel):
    submitter_name: str | None = Field(default=None, max_length=80)
    company_name: str = Field(min_length=2, max_length=100)
    position_name: str = Field(min_length=2, max_length=50)
    title: str = Field(min_length=6, max_length=300)
    body: str | None = Field(default=None, max_length=4000)
    answer_key: str = Field(min_length=20, max_length=8000)
    difficulty: int = Field(default=3, ge=1, le=5)
    qtype: Literal["behavioral", "knowledge", "coding", "system_design"]
    tags: list[str] = Field(default_factory=list, max_length=10)


class SubmissionOut(BaseModel):
    id: int
    submitter_name: str | None = None
    company_name: str
    position_name: str
    title: str
    body: str | None = None
    answer_key: str
    difficulty: int
    qtype: str
    source_type: str
    tags: list[dict[str, Any]] = Field(default_factory=list)
    status: str
    review_note: str | None = None
    created_question_id: int | None = None
    created_at: datetime
    reviewed_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class ReviewSubmissionRequest(BaseModel):
    action: Literal["approve", "reject"]
    note: str | None = Field(default=None, max_length=1000)


class GenerateFromJdRequest(BaseModel):
    jd_text: str = Field(min_length=30, max_length=20000)
    company: str = Field(min_length=2, max_length=100)
    position: str = Field(min_length=2, max_length=50)
    count: int = Field(default=5, ge=1, le=10)


class GeneratedSubmissionOut(BaseModel):
    items: list[SubmissionOut]
