from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Index, Integer, Numeric, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, UserDefinedType


jsonb_type = JSONB().with_variant(JSON(), "sqlite")
bigint_type = BigInteger().with_variant(Integer(), "sqlite")


class Vector(UserDefinedType):
    cache_ok = True

    def __init__(self, dimensions: int) -> None:
        self.dimensions = dimensions

    def get_col_spec(self, **_: Any) -> str:
        return f"vector({self.dimensions})"


class Base(DeclarativeBase):
    pass


class Company(Base):
    __tablename__ = "companies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    name_en: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str] = mapped_column(String(20), nullable=False, default="CN")
    tier: Mapped[int | None] = mapped_column(SmallInteger, default=1)
    logo_url: Mapped[str | None] = mapped_column(Text)

    questions: Mapped[list[Question]] = relationship(back_populates="company")


class Position(Base):
    __tablename__ = "positions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)

    questions: Mapped[list[Question]] = relationship(back_populates="position")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    category: Mapped[str | None] = mapped_column(String(30))

    question_links: Mapped[list[QuestionTag]] = relationship(back_populates="tag", cascade="all, delete-orphan")


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (Index("idx_q_company_pos", "company_id", "position_id", "status"),)

    id: Mapped[int] = mapped_column(bigint_type, primary_key=True)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    answer_key: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    qtype: Mapped[str] = mapped_column(String(20), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False)
    source_note: Mapped[str | None] = mapped_column(Text)
    company_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("companies.id"))
    position_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("positions.id"))
    embedding: Mapped[Any | None] = mapped_column(Vector(1024))
    status: Mapped[str] = mapped_column(String(15), default="active")
    ask_count: Mapped[int] = mapped_column(Integer, default=0)
    created_by_user_id: Mapped[int | None] = mapped_column(bigint_type, ForeignKey("users.id"))
    updated_by_user_id: Mapped[int | None] = mapped_column(bigint_type, ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())
    published_at: Mapped[datetime | None]
    archived_at: Mapped[datetime | None]
    default_rubric_version_id: Mapped[int | None] = mapped_column(bigint_type, ForeignKey("scoring_rubric_versions.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    company: Mapped[Company | None] = relationship(back_populates="questions")
    position: Mapped[Position | None] = relationship(back_populates="questions")
    tag_links: Mapped[list[QuestionTag]] = relationship(back_populates="question", cascade="all, delete-orphan")
    session_questions: Mapped[list[SessionQuestion]] = relationship(back_populates="question")
    evaluation_results: Mapped[list[EvaluationResult]] = relationship(back_populates="question")
    default_rubric_version: Mapped[ScoringRubricVersion | None] = relationship(back_populates="default_questions")


class QuestionTag(Base):
    __tablename__ = "question_tags"

    question_id: Mapped[int] = mapped_column(bigint_type, ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("tags.id"), primary_key=True)

    question: Mapped[Question] = relationship(back_populates="tag_links")
    tag: Mapped[Tag] = relationship(back_populates="question_links")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(bigint_type, primary_key=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True)
    nickname: Mapped[str | None] = mapped_column(String(50))
    target_company_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("companies.id"))
    target_position_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("positions.id"))
    level: Mapped[str] = mapped_column(String(20), default="junior")
    role: Mapped[str] = mapped_column(String(30), nullable=False, default="user")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    sessions: Mapped[list[Session]] = relationship(back_populates="user")
    practice_plans: Mapped[list[PracticePlan]] = relationship(back_populates="user")
    evaluation_results: Mapped[list[EvaluationResult]] = relationship(back_populates="user")
    llm_usage_records: Mapped[list[LLMUsageRecord]] = relationship(back_populates="user")
    created_rubrics: Mapped[list[ScoringRubric]] = relationship(
        back_populates="created_by",
        foreign_keys="ScoringRubric.created_by_user_id",
    )
    created_rubric_versions: Mapped[list[ScoringRubricVersion]] = relationship(
        back_populates="created_by",
        foreign_keys="ScoringRubricVersion.created_by_user_id",
    )


class ScoringRubric(Base):
    __tablename__ = "scoring_rubrics"
    __table_args__ = (
        Index("idx_scoring_rubrics_status", "status"),
        Index("idx_scoring_rubrics_name", "name"),
    )

    id: Mapped[int] = mapped_column(bigint_type, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False, unique=True)
    description: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(15), nullable=False, default="draft")
    created_by_user_id: Mapped[int | None] = mapped_column(bigint_type, ForeignKey("users.id"))
    updated_by_user_id: Mapped[int | None] = mapped_column(bigint_type, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    versions: Mapped[list[ScoringRubricVersion]] = relationship(back_populates="rubric", cascade="all, delete-orphan")
    created_by: Mapped[User | None] = relationship(back_populates="created_rubrics", foreign_keys=[created_by_user_id])


class ScoringRubricVersion(Base):
    __tablename__ = "scoring_rubric_versions"
    __table_args__ = (
        Index("idx_rubric_versions_rubric_status", "rubric_id", "status"),
        Index("idx_rubric_versions_status_created", "status", "created_at"),
    )

    id: Mapped[int] = mapped_column(bigint_type, primary_key=True)
    rubric_id: Mapped[int] = mapped_column(bigint_type, ForeignKey("scoring_rubrics.id"), nullable=False)
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    dimensions_json: Mapped[list[dict[str, Any]]] = mapped_column(jsonb_type, default=list)
    prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    scoring_scale: Mapped[str] = mapped_column(String(40), nullable=False, default="0-100")
    status: Mapped[str] = mapped_column(String(15), nullable=False, default="draft")
    created_by_user_id: Mapped[int | None] = mapped_column(bigint_type, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    published_at: Mapped[datetime | None]
    archived_at: Mapped[datetime | None]

    rubric: Mapped[ScoringRubric] = relationship(back_populates="versions")
    created_by: Mapped[User | None] = relationship(back_populates="created_rubric_versions", foreign_keys=[created_by_user_id])
    default_questions: Mapped[list[Question]] = relationship(back_populates="default_rubric_version")
    evaluation_results: Mapped[list[EvaluationResult]] = relationship(back_populates="rubric_version")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(bigint_type, primary_key=True)
    user_id: Mapped[int] = mapped_column(bigint_type, ForeignKey("users.id"), nullable=False)
    mode: Mapped[str] = mapped_column(String(15), nullable=False)
    company_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("companies.id"))
    position_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("positions.id"))
    status: Mapped[str] = mapped_column(String(15), default="created")
    report: Mapped[dict[str, Any] | None] = mapped_column(jsonb_type)
    started_at: Mapped[datetime] = mapped_column(server_default=func.now())
    deadline_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
    expired_at: Mapped[datetime | None]
    ended_at: Mapped[datetime | None]
    current_question_id: Mapped[int | None] = mapped_column(bigint_type, ForeignKey("questions.id"))
    current_question_index: Mapped[int] = mapped_column(SmallInteger, default=1)
    total_questions: Mapped[int] = mapped_column(SmallInteger, default=1)
    max_followups: Mapped[int] = mapped_column(SmallInteger, default=3)
    current_followups: Mapped[int] = mapped_column(SmallInteger, default=0)
    end_reason: Mapped[str | None] = mapped_column(String(30))
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    user: Mapped[User] = relationship(back_populates="sessions")
    questions: Mapped[list[SessionQuestion]] = relationship(back_populates="session", cascade="all, delete-orphan")
    evaluation_results: Mapped[list[EvaluationResult]] = relationship(back_populates="session", cascade="all, delete-orphan")
    llm_usage_records: Mapped[list[LLMUsageRecord]] = relationship(back_populates="session")


class SessionQuestion(Base):
    __tablename__ = "session_questions"

    id: Mapped[int] = mapped_column(bigint_type, primary_key=True)
    session_id: Mapped[int] = mapped_column(bigint_type, ForeignKey("sessions.id"), nullable=False)
    question_id: Mapped[int] = mapped_column(bigint_type, ForeignKey("questions.id"), nullable=False)
    order_no: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    status: Mapped[str] = mapped_column(String(15), default="pending")
    started_at: Mapped[datetime | None]
    submitted_at: Mapped[datetime | None]
    scored_at: Mapped[datetime | None]
    answer_text: Mapped[str | None] = mapped_column(Text)
    verdict: Mapped[dict[str, Any] | None] = mapped_column(jsonb_type)
    followup_count: Mapped[int] = mapped_column(SmallInteger, default=0)
    final_score: Mapped[int | None] = mapped_column(SmallInteger)
    mastery: Mapped[str | None] = mapped_column(String(10))
    finished_at: Mapped[datetime | None]

    session: Mapped[Session] = relationship(back_populates="questions")
    question: Mapped[Question] = relationship(back_populates="session_questions")
    messages: Mapped[list[Message]] = relationship(back_populates="session_question", cascade="all, delete-orphan")
    evaluation_results: Mapped[list[EvaluationResult]] = relationship(back_populates="session_question", cascade="all, delete-orphan")


class EvaluationResult(Base):
    __tablename__ = "evaluation_results"
    __table_args__ = (
        Index("idx_eval_user_created", "user_id", "created_at"),
        Index("idx_eval_session_question", "session_id", "sq_id"),
    )

    id: Mapped[int] = mapped_column(bigint_type, primary_key=True)
    user_id: Mapped[int] = mapped_column(bigint_type, ForeignKey("users.id"), nullable=False)
    session_id: Mapped[int] = mapped_column(bigint_type, ForeignKey("sessions.id"), nullable=False)
    sq_id: Mapped[int] = mapped_column(bigint_type, ForeignKey("session_questions.id"), nullable=False)
    question_id: Mapped[int] = mapped_column(bigint_type, ForeignKey("questions.id"), nullable=False)
    score: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    mastery: Mapped[str] = mapped_column(String(10), nullable=False)
    verdict: Mapped[str] = mapped_column(Text, nullable=False)
    strengths: Mapped[list[str]] = mapped_column(jsonb_type, default=list)
    missing_points: Mapped[list[str]] = mapped_column(jsonb_type, default=list)
    expression_issues: Mapped[list[str]] = mapped_column(jsonb_type, default=list)
    followup_failures: Mapped[list[str]] = mapped_column(jsonb_type, default=list)
    action_items: Mapped[list[str]] = mapped_column(jsonb_type, default=list)
    recommended_questions: Mapped[list[dict[str, Any]]] = mapped_column(jsonb_type, default=list)
    raw_model_output: Mapped[dict[str, Any]] = mapped_column(jsonb_type, default=dict)
    model_name: Mapped[str] = mapped_column(String(80), nullable=False, default="local-fallback")
    prompt_version: Mapped[str] = mapped_column(String(40), nullable=False, default="interviewer-v1")
    rubric_version_id: Mapped[int | None] = mapped_column(bigint_type, ForeignKey("scoring_rubric_versions.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped[User] = relationship(back_populates="evaluation_results")
    session: Mapped[Session] = relationship(back_populates="evaluation_results")
    session_question: Mapped[SessionQuestion] = relationship(back_populates="evaluation_results")
    question: Mapped[Question] = relationship(back_populates="evaluation_results")
    rubric_version: Mapped[ScoringRubricVersion | None] = relationship(back_populates="evaluation_results")


class LLMUsageRecord(Base):
    __tablename__ = "llm_usage_records"
    __table_args__ = (
        Index("idx_llm_usage_user_created", "user_id", "created_at"),
        Index("idx_llm_usage_user_feature", "user_id", "feature"),
        Index("idx_llm_usage_request_id", "request_id"),
    )

    id: Mapped[int] = mapped_column(bigint_type, primary_key=True)
    user_id: Mapped[int] = mapped_column(bigint_type, ForeignKey("users.id"), nullable=False)
    session_id: Mapped[int | None] = mapped_column(bigint_type, ForeignKey("sessions.id"))
    request_id: Mapped[str | None] = mapped_column(String(80))
    feature: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown")
    provider: Mapped[str] = mapped_column(String(30), nullable=False, default="unknown")
    model: Mapped[str] = mapped_column(String(80), nullable=False, default="unknown")
    prompt_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    completion_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    total_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    estimated_cost: Mapped[Decimal] = mapped_column(Numeric(12, 6), nullable=False, default=0)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="USD")
    pricing_version: Mapped[str] = mapped_column(String(40), nullable=False)
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(15), nullable=False, default="success")
    error_type: Mapped[str | None] = mapped_column(String(80))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped[User] = relationship(back_populates="llm_usage_records")
    session: Mapped[Session | None] = relationship(back_populates="llm_usage_records")


class AuditEvent(Base):
    __tablename__ = "audit_events"
    __table_args__ = (
        Index("idx_audit_actor_created", "actor_user_id", "created_at"),
        Index("idx_audit_action_created", "action", "created_at"),
        Index("idx_audit_request_id", "request_id"),
    )

    id: Mapped[int] = mapped_column(bigint_type, primary_key=True)
    actor_user_id: Mapped[int | None] = mapped_column(bigint_type, ForeignKey("users.id"))
    actor_phone_masked: Mapped[str | None] = mapped_column(String(20))
    actor_role: Mapped[str] = mapped_column(String(20), nullable=False, default="anonymous")
    action: Mapped[str] = mapped_column(String(50), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(50))
    resource_id: Mapped[str | None] = mapped_column(String(80))
    target_user_id: Mapped[int | None] = mapped_column(bigint_type, ForeignKey("users.id"))
    request_id: Mapped[str | None] = mapped_column(String(80))
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(120))
    ip_address: Mapped[str | None] = mapped_column(String(80))
    user_agent: Mapped[str | None] = mapped_column(String(300))
    metadata_json: Mapped[dict[str, Any]] = mapped_column(jsonb_type, default=dict)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("idx_msg_sq", "sq_id", "id"),)

    id: Mapped[int] = mapped_column(bigint_type, primary_key=True)
    sq_id: Mapped[int] = mapped_column(bigint_type, ForeignKey("session_questions.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(12), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    msg_type: Mapped[str] = mapped_column(String(15), nullable=False)
    eval_json: Mapped[dict[str, Any] | None] = mapped_column(jsonb_type)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    session_question: Mapped[SessionQuestion] = relationship(back_populates="messages")


class WrongBook(Base):
    __tablename__ = "wrong_book"

    user_id: Mapped[int] = mapped_column(bigint_type, ForeignKey("users.id"), primary_key=True)
    question_id: Mapped[int] = mapped_column(bigint_type, ForeignKey("questions.id"), primary_key=True)
    last_score: Mapped[int | None] = mapped_column(SmallInteger)
    fail_count: Mapped[int] = mapped_column(SmallInteger, default=1)
    next_review: Mapped[date | None] = mapped_column(Date)


class UserTagStat(Base):
    __tablename__ = "user_tag_stats"

    user_id: Mapped[int] = mapped_column(bigint_type, ForeignKey("users.id"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("tags.id"), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    avg_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)


class PracticePlan(Base):
    __tablename__ = "practice_plans"
    __table_args__ = (
        Index("idx_practice_plan_user_date", "user_id", "plan_date", unique=True),
        Index("idx_practice_plan_completed", "user_id", "completed"),
    )

    id: Mapped[int] = mapped_column(bigint_type, primary_key=True)
    user_id: Mapped[int] = mapped_column(bigint_type, ForeignKey("users.id"), nullable=False)
    plan_date: Mapped[date] = mapped_column(Date, nullable=False)
    recommended_tasks: Mapped[list[dict[str, Any]]] = mapped_column(jsonb_type, default=list)
    weak_tags: Mapped[list[dict[str, Any]]] = mapped_column(jsonb_type, default=list)
    target_abilities: Mapped[list[str]] = mapped_column(jsonb_type, default=list)
    generated_reason: Mapped[str] = mapped_column(Text, nullable=False)
    completed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    user: Mapped[User] = relationship(back_populates="practice_plans")


class QuestionSubmission(Base):
    __tablename__ = "question_submissions"
    __table_args__ = (Index("idx_submission_status_created", "status", "created_at"),)

    id: Mapped[int] = mapped_column(bigint_type, primary_key=True)
    submitter_name: Mapped[str | None] = mapped_column(String(80))
    company_name: Mapped[str] = mapped_column(String(100), nullable=False)
    position_name: Mapped[str] = mapped_column(String(50), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    body: Mapped[str | None] = mapped_column(Text)
    answer_key: Mapped[str] = mapped_column(Text, nullable=False)
    difficulty: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    qtype: Mapped[str] = mapped_column(String(20), nullable=False)
    source_type: Mapped[str] = mapped_column(String(20), nullable=False, default="ugc")
    tags: Mapped[list[dict[str, Any]]] = mapped_column(jsonb_type, default=list)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending_review")
    review_note: Mapped[str | None] = mapped_column(Text)
    created_question_id: Mapped[int | None] = mapped_column(bigint_type, ForeignKey("questions.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    reviewed_at: Mapped[datetime | None]
