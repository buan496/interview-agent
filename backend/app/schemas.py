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


class QuestionBankQuestionOut(QuestionOut):
    answer_reference: str
    status: str
    default_rubric_version_id: int | None = None
    created_by_user_id: int | None = None
    updated_by_user_id: int | None = None
    created_at: datetime
    updated_at: datetime | None = None
    published_at: datetime | None = None
    archived_at: datetime | None = None


class QuestionBankListOut(BaseModel):
    items: list[QuestionBankQuestionOut]
    total: int


class QuestionBankCreateRequest(BaseModel):
    title: str = Field(min_length=6, max_length=300)
    prompt: str | None = Field(default=None, max_length=4000)
    answer_reference: str = Field(min_length=20, max_length=8000)
    difficulty: int = Field(default=3, ge=1, le=5)
    qtype: Literal["behavioral", "knowledge", "coding", "system_design"]
    company_id: int | None = None
    company_name: str | None = Field(default=None, min_length=2, max_length=100)
    position_id: int | None = None
    position_name: str | None = Field(default=None, min_length=2, max_length=50)
    tags: list[str] = Field(default_factory=list, max_length=10)
    source_note: str | None = Field(default=None, max_length=1000)
    status: Literal["draft", "published"] = "draft"
    default_rubric_version_id: int | None = Field(default=None, ge=1)


class QuestionBankUpdateRequest(BaseModel):
    title: str | None = Field(default=None, min_length=6, max_length=300)
    prompt: str | None = Field(default=None, max_length=4000)
    answer_reference: str | None = Field(default=None, min_length=20, max_length=8000)
    difficulty: int | None = Field(default=None, ge=1, le=5)
    qtype: Literal["behavioral", "knowledge", "coding", "system_design"] | None = None
    company_id: int | None = None
    company_name: str | None = Field(default=None, min_length=2, max_length=100)
    position_id: int | None = None
    position_name: str | None = Field(default=None, min_length=2, max_length=50)
    tags: list[str] | None = Field(default=None, max_length=10)
    source_note: str | None = Field(default=None, max_length=1000)
    default_rubric_version_id: int | None = Field(default=None, ge=1)


class RubricVersionOut(BaseModel):
    id: int
    rubric_id: int
    version: str
    dimensions_json: list[dict[str, Any]] = Field(default_factory=list)
    prompt_template: str
    scoring_scale: str
    status: str
    created_by_user_id: int | None = None
    created_at: datetime
    published_at: datetime | None = None
    archived_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class RubricOut(BaseModel):
    id: int
    name: str
    description: str | None = None
    status: str
    created_by_user_id: int | None = None
    updated_by_user_id: int | None = None
    created_at: datetime
    updated_at: datetime | None = None
    versions: list[RubricVersionOut] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True)


class RubricListOut(BaseModel):
    items: list[RubricOut]
    total: int


class RubricCreateRequest(BaseModel):
    name: str = Field(min_length=3, max_length=120)
    description: str | None = Field(default=None, max_length=2000)
    status: Literal["draft", "published"] = "draft"


class RubricVersionCreateRequest(BaseModel):
    version: str = Field(min_length=1, max_length=40)
    dimensions_json: list[dict[str, Any]] = Field(default_factory=list, max_length=20)
    prompt_template: str = Field(min_length=20, max_length=8000)
    scoring_scale: str = Field(default="0-100", min_length=3, max_length=40)


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
    strengths: list[str] = Field(default_factory=list)
    missing_points: list[str] = Field(default_factory=list)
    expression_issues: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    recommended_questions: list[dict[str, Any]] = Field(default_factory=list)
    rubric_version_id: int | None = None
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


class TrainingHistoryItemOut(BaseModel):
    session_id: int
    report_id: int | None = None
    mode: str
    title: str
    status: str
    overall_score: int | None = None
    question_count: int
    started_at: datetime
    completed_at: datetime | None = None
    created_at: datetime
    weak_tags: list[str] = Field(default_factory=list)
    next_action: Literal["continue", "view_report", "review_wrong_book"]


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


class AbilityTagProfileOut(BaseModel):
    tag_id: int
    tag: str
    category: str | None = None
    average_score: Decimal
    practice_count: int
    wrong_count: int
    mastery_level: Literal["strong", "stable", "weak"]
    last_practiced_at: datetime | None = None


class AbilityProfileOut(BaseModel):
    overall_score: int | None = None
    total_sessions: int
    completed_sessions: int
    total_questions: int
    updated_at: datetime | None = None
    strengths: list[AbilityTagProfileOut] = Field(default_factory=list)
    weaknesses: list[AbilityTagProfileOut] = Field(default_factory=list)
    tag_profiles: list[AbilityTagProfileOut] = Field(default_factory=list)


class AgentMemoryOut(BaseModel):
    id: int
    memory_type: str
    title: str
    summary: str
    tags_json: list[dict[str, Any]] = Field(default_factory=list)
    evidence_json: list[dict[str, Any]] = Field(default_factory=list)
    confidence: Decimal
    status: str
    source_type: str
    source_id: int | None = None
    first_seen_at: datetime | None = None
    last_seen_at: datetime | None = None
    created_at: datetime
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AgentMemoryListOut(BaseModel):
    items: list[AgentMemoryOut]
    total: int


class AgentMemoryRefreshOut(BaseModel):
    created: int
    updated: int
    total_active: int


class AsyncJobOut(BaseModel):
    id: int
    job_type: str
    status: str
    payload_json: dict[str, Any] = Field(default_factory=dict)
    result_json: dict[str, Any] | None = None
    error_type: str | None = None
    error_message: str | None = None
    attempts: int
    max_attempts: int
    idempotency_key: str | None = None
    created_at: datetime
    started_at: datetime | None = None
    finished_at: datetime | None = None
    updated_at: datetime | None = None

    model_config = ConfigDict(from_attributes=True)


class AsyncJobListOut(BaseModel):
    items: list[AsyncJobOut]
    total: int


class AsyncJobCreateOut(BaseModel):
    job_id: int
    status: str
    job: AsyncJobOut


class LLMUsageBreakdownOut(BaseModel):
    key: str
    call_count: int
    failed_count: int
    total_tokens: int
    estimated_cost: Decimal


class LLMUsageRecordOut(BaseModel):
    id: int
    session_id: int | None = None
    request_id: str | None = None
    feature: str
    provider: str
    model: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: Decimal
    currency: str
    pricing_version: str
    latency_ms: int | None = None
    status: str
    error_type: str | None = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class LLMUsageSummaryOut(BaseModel):
    total_tokens: int
    total_estimated_cost: Decimal
    current_month_tokens: int
    current_month_estimated_cost: Decimal
    currency: str
    pricing_version: str
    by_feature: list[LLMUsageBreakdownOut] = Field(default_factory=list)
    by_model: list[LLMUsageBreakdownOut] = Field(default_factory=list)
    recent_records: list[LLMUsageRecordOut] = Field(default_factory=list)


class DataSummaryOut(BaseModel):
    scope: str
    counts: dict[str, int] = Field(default_factory=dict)


class DataExportOut(BaseModel):
    export_version: str
    user: dict[str, Any] = Field(default_factory=dict)
    summary: DataSummaryOut
    sessions: list[dict[str, Any]] = Field(default_factory=list)
    session_questions: list[dict[str, Any]] = Field(default_factory=list)
    evaluation_results: list[dict[str, Any]] = Field(default_factory=list)
    reports: list[dict[str, Any]] = Field(default_factory=list)
    wrong_book: list[dict[str, Any]] = Field(default_factory=list)
    user_tag_stats: list[dict[str, Any]] = Field(default_factory=list)
    practice_plans: list[dict[str, Any]] = Field(default_factory=list)
    agent_memories: list[dict[str, Any]] = Field(default_factory=list)
    async_jobs: list[dict[str, Any]] = Field(default_factory=list)
    llm_usage_records: list[dict[str, Any]] = Field(default_factory=list)


class DataDeletionRequestOut(BaseModel):
    scope: str
    confirmation_phrase: str
    impact: dict[str, int] = Field(default_factory=dict)
    warning: str


class DataDeletionConfirmRequest(BaseModel):
    confirmation_phrase: str = Field(min_length=1, max_length=80)


class DataDeletionOut(BaseModel):
    scope: str
    deleted_counts: dict[str, int] = Field(default_factory=dict)


class AuditEventOut(BaseModel):
    id: int
    actor_user_id: int | None = None
    actor_phone_masked: str | None = None
    actor_role: str
    action: str
    resource_type: str | None = None
    resource_id: str | None = None
    target_user_id: int | None = None
    request_id: str | None = None
    status: str
    reason: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    metadata_json: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


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
