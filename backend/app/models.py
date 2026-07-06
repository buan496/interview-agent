from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Boolean, Date, ForeignKey, Index, Integer, Numeric, SmallInteger, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import JSON, UserDefinedType


jsonb_type = JSONB().with_variant(JSON(), "sqlite")


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

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
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
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    company: Mapped[Company | None] = relationship(back_populates="questions")
    position: Mapped[Position | None] = relationship(back_populates="questions")
    tag_links: Mapped[list[QuestionTag]] = relationship(back_populates="question", cascade="all, delete-orphan")
    session_questions: Mapped[list[SessionQuestion]] = relationship(back_populates="question")
    evaluation_results: Mapped[list[EvaluationResult]] = relationship(back_populates="question")


class QuestionTag(Base):
    __tablename__ = "question_tags"

    question_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("questions.id", ondelete="CASCADE"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("tags.id"), primary_key=True)

    question: Mapped[Question] = relationship(back_populates="tag_links")
    tag: Mapped[Tag] = relationship(back_populates="question_links")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    phone: Mapped[str | None] = mapped_column(String(20), unique=True)
    nickname: Mapped[str | None] = mapped_column(String(50))
    target_company_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("companies.id"))
    target_position_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("positions.id"))
    level: Mapped[str] = mapped_column(String(20), default="junior")
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    sessions: Mapped[list[Session]] = relationship(back_populates="user")
    practice_plans: Mapped[list[PracticePlan]] = relationship(back_populates="user")
    evaluation_results: Mapped[list[EvaluationResult]] = relationship(back_populates="user")


class Session(Base):
    __tablename__ = "sessions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
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
    current_question_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("questions.id"))
    current_question_index: Mapped[int] = mapped_column(SmallInteger, default=1)
    total_questions: Mapped[int] = mapped_column(SmallInteger, default=1)
    max_followups: Mapped[int] = mapped_column(SmallInteger, default=3)
    current_followups: Mapped[int] = mapped_column(SmallInteger, default=0)
    end_reason: Mapped[str | None] = mapped_column(String(30))
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now())

    user: Mapped[User] = relationship(back_populates="sessions")
    questions: Mapped[list[SessionQuestion]] = relationship(back_populates="session", cascade="all, delete-orphan")
    evaluation_results: Mapped[list[EvaluationResult]] = relationship(back_populates="session", cascade="all, delete-orphan")


class SessionQuestion(Base):
    __tablename__ = "session_questions"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    session_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sessions.id"), nullable=False)
    question_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("questions.id"), nullable=False)
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

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
    session_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("sessions.id"), nullable=False)
    sq_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("session_questions.id"), nullable=False)
    question_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("questions.id"), nullable=False)
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
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    user: Mapped[User] = relationship(back_populates="evaluation_results")
    session: Mapped[Session] = relationship(back_populates="evaluation_results")
    session_question: Mapped[SessionQuestion] = relationship(back_populates="evaluation_results")
    question: Mapped[Question] = relationship(back_populates="evaluation_results")


class Message(Base):
    __tablename__ = "messages"
    __table_args__ = (Index("idx_msg_sq", "sq_id", "id"),)

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    sq_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("session_questions.id"), nullable=False)
    role: Mapped[str] = mapped_column(String(12), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    msg_type: Mapped[str] = mapped_column(String(15), nullable=False)
    eval_json: Mapped[dict[str, Any] | None] = mapped_column(jsonb_type)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())

    session_question: Mapped[SessionQuestion] = relationship(back_populates="messages")


class WrongBook(Base):
    __tablename__ = "wrong_book"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), primary_key=True)
    question_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("questions.id"), primary_key=True)
    last_score: Mapped[int | None] = mapped_column(SmallInteger)
    fail_count: Mapped[int] = mapped_column(SmallInteger, default=1)
    next_review: Mapped[date | None] = mapped_column(Date)


class UserTagStat(Base):
    __tablename__ = "user_tag_stats"

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), primary_key=True)
    tag_id: Mapped[int] = mapped_column(Integer, ForeignKey("tags.id"), primary_key=True)
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    avg_score: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=0)


class PracticePlan(Base):
    __tablename__ = "practice_plans"
    __table_args__ = (
        Index("idx_practice_plan_user_date", "user_id", "plan_date", unique=True),
        Index("idx_practice_plan_completed", "user_id", "completed"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("users.id"), nullable=False)
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

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
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
    created_question_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("questions.id"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    reviewed_at: Mapped[datetime | None]
