from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import date, datetime, timedelta, timezone
from time import perf_counter

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.api.auth import get_current_user
from app.core.interviewer import ConversationMessage, InterviewerEngine, InterviewQuestion
from app.core.scheduler import target_question_count, target_type_counts
from app.db import SessionLocal, get_db
from app.llm_usage import (
    elapsed_ms,
    estimate_completion_tokens,
    estimate_prompt_tokens,
    feature_from_result,
    model_from_llm,
    provider_from_llm,
    record_llm_usage,
    usage_metering_enabled,
)
from app.models import EvaluationResult, Message, Question, QuestionTag, Session, SessionQuestion, User, UserTagStat, WrongBook
from app.observability import log_event
from app.schemas import (
    AnswerRequest,
    CreateSessionOut,
    CreateSessionRequest,
    FirstQuestionOut,
    MessageOut,
    RadarItemOut,
    ReportQuestionOut,
    SessionDetailOut,
    TrainingHistoryItemOut,
    SessionQuestionOut,
    SessionReportOut,
    TagOut,
)


router = APIRouter(prefix="/sessions", tags=["sessions"])

ACTIVE_SESSION_STATUSES = {"created", "ongoing", "paused"}
ANSWERABLE_SESSION_STATUSES = {"ongoing"}
TERMINAL_SESSION_STATUSES = {"finished", "expired", "cancelled"}
DEFAULT_MAX_FOLLOWUPS = 3
PROMPT_VERSION = "interviewer-v1"


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _session_duration(mode: str) -> timedelta:
    return timedelta(minutes=45 if mode == "mock" else 20)


def _remaining_seconds(session: Session, now: datetime | None = None) -> int | None:
    deadline = _as_utc(session.deadline_at)
    if deadline is None:
        return None
    current = now or _now()
    return max(0, int((deadline - current).total_seconds()))


def _expire_if_needed(session: Session, now: datetime | None = None) -> bool:
    current = now or _now()
    deadline = _as_utc(session.deadline_at)
    if session.status in TERMINAL_SESSION_STATUSES or deadline is None or current <= deadline:
        return False
    session.status = "expired"
    session.expired_at = current
    session.ended_at = current
    session.end_reason = "timeout"
    for sq in session.questions:
        if sq.status in {"pending", "answering"}:
            sq.status = "timeout"
    return True


def _assert_answerable(session: Session, now: datetime | None = None) -> None:
    _expire_if_needed(session, now)
    if session.status == "expired":
        raise HTTPException(status_code=409, detail="Session expired")
    if session.status not in ANSWERABLE_SESSION_STATUSES:
        raise HTTPException(status_code=409, detail=f"Session is not answerable: {session.status}")


def _tags(question: Question) -> list[TagOut]:
    return [TagOut.model_validate(link.tag) for link in question.tag_links]


def _first_question(question: Question, sq_id: int) -> FirstQuestionOut:
    return FirstQuestionOut(
        sq_id=sq_id,
        title=question.title,
        body=question.body,
        difficulty=question.difficulty,
        qtype=question.qtype,
        tags=_tags(question),
    )


def _question_filter_stmt(request: CreateSessionRequest):
    stmt = select(Question).where(Question.status == "active")
    if request.question_id:
        stmt = stmt.where(Question.id == request.question_id)
    if request.company_id:
        stmt = stmt.where(Question.company_id == request.company_id)
    if request.position_id:
        stmt = stmt.where(Question.position_id == request.position_id)
    if request.difficulty:
        stmt = stmt.where(Question.difficulty == request.difficulty)
    if request.tag_ids:
        stmt = stmt.join(QuestionTag).where(QuestionTag.tag_id.in_(request.tag_ids)).distinct()
    return stmt


async def _select_question(db: AsyncSession, request: CreateSessionRequest) -> Question | None:
    stmt = _question_filter_stmt(request)
    stmt = stmt.options(
        selectinload(Question.company),
        selectinload(Question.position),
        selectinload(Question.tag_links).selectinload(QuestionTag.tag),
    ).order_by(func.random()).limit(1)
    return (await db.execute(stmt)).scalar_one_or_none()


async def _select_mock_questions(db: AsyncSession, request: CreateSessionRequest) -> list[Question]:
    total = target_question_count()
    counts = target_type_counts(total)
    selected: list[Question] = []
    selected_ids: set[int] = set()
    eager = (
        selectinload(Question.company),
        selectinload(Question.position),
        selectinload(Question.tag_links).selectinload(QuestionTag.tag),
    )

    for qtype, count in counts.items():
        rows = await db.execute(
            _question_filter_stmt(request)
            .where(Question.qtype == qtype)
            .options(*eager)
            .order_by(func.random())
            .limit(count)
        )
        for question in rows.scalars().all():
            if question.id not in selected_ids:
                selected.append(question)
                selected_ids.add(question.id)

    if len(selected) < total:
        rows = await db.execute(
            _question_filter_stmt(request)
            .where(Question.id.not_in(selected_ids) if selected_ids else True)
            .options(*eager)
            .order_by(func.random())
            .limit(total - len(selected))
        )
        selected.extend(rows.scalars().all())
    return selected


@router.post("", response_model=CreateSessionOut)
async def create_session(
    request: CreateSessionRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CreateSessionOut:
    questions = (
        await _select_mock_questions(db, request)
        if request.mode == "mock"
        else [question] if (question := await _select_question(db, request)) else []
    )
    if not questions:
        log_event("session.create", status="not_found", mode=request.mode)
        raise HTTPException(status_code=404, detail="No active question matched filters")

    now = _now()
    session = Session(
        user_id=current_user.id,
        mode=request.mode,
        company_id=request.company_id or questions[0].company_id,
        position_id=request.position_id or questions[0].position_id,
        status="ongoing",
        started_at=now,
        deadline_at=now + _session_duration(request.mode),
        current_question_id=questions[0].id,
        current_question_index=1,
        total_questions=len(questions),
        max_followups=DEFAULT_MAX_FOLLOWUPS,
        current_followups=0,
    )
    db.add(session)
    await db.flush()

    first_sq: SessionQuestion | None = None
    for order_no, question in enumerate(questions, start=1):
        sq = SessionQuestion(
            session_id=session.id,
            question_id=question.id,
            order_no=order_no,
            status="answering" if order_no == 1 else "pending",
            started_at=now if order_no == 1 else None,
        )
        db.add(sq)
        question.ask_count += 1
        await db.flush()
        if first_sq is None:
            first_sq = sq

    assert first_sq is not None
    db.add(Message(sq_id=first_sq.id, role="interviewer", content=questions[0].title, msg_type="question"))
    await db.commit()
    log_event("session.create", status="success", session_id=session.id, mode=session.mode, question_count=len(questions))
    return CreateSessionOut(
        session_id=session.id,
        first_question=_first_question(questions[0], first_sq.id),
        status=session.status,
        server_now=now,
        deadline_at=session.deadline_at,
        remaining_seconds=_remaining_seconds(session, now),
    )


def _history_next_action(session: Session) -> str:
    if session.status == "finished":
        return "view_report"
    if session.status in ACTIVE_SESSION_STATUSES:
        return "continue"
    return "review_wrong_book"


def _history_weak_tags(session: Session) -> list[str]:
    report = session.report or {}
    questions = report.get("questions", []) if isinstance(report, dict) else []
    weak_tags: list[str] = []
    if isinstance(questions, list):
        for item in questions:
            if not isinstance(item, dict) or item.get("mastery") not in {"weak", "fail"}:
                continue
            for tag in item.get("tags", []) or []:
                if isinstance(tag, dict) and isinstance(tag.get("name"), str) and tag["name"] not in weak_tags:
                    weak_tags.append(tag["name"])
    radar = report.get("radar", []) if isinstance(report, dict) else []
    if isinstance(radar, list):
        for item in radar:
            if not isinstance(item, dict):
                continue
            score = item.get("avg_score", 100)
            tag = item.get("tag")
            if isinstance(tag, str) and isinstance(score, (int, float)) and score < 70 and tag not in weak_tags:
                weak_tags.append(tag)
    return weak_tags[:5]


def _history_title(session: Session) -> str:
    first_question = next((item for item in sorted(session.questions, key=lambda value: value.order_no) if item.question), None)
    if first_question:
        return first_question.question.title
    return "模拟面试" if session.mode == "mock" else "单题训练"


def _history_item(session: Session) -> TrainingHistoryItemOut:
    report = session.report or {}
    overall_score = report.get("overall_score") if isinstance(report, dict) else None
    return TrainingHistoryItemOut(
        session_id=session.id,
        report_id=session.id if session.status == "finished" else None,
        mode=session.mode,
        title=_history_title(session),
        status=session.status,
        overall_score=int(overall_score) if overall_score is not None else None,
        question_count=session.total_questions,
        started_at=session.started_at,
        completed_at=session.ended_at or session.finished_at,
        created_at=session.started_at,
        weak_tags=_history_weak_tags(session),
        next_action=_history_next_action(session),
    )


@router.get("/history", response_model=list[TrainingHistoryItemOut])
async def training_history(
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> list[TrainingHistoryItemOut]:
    rows = (
        await db.execute(
            select(Session)
            .where(Session.user_id == current_user.id)
            .options(selectinload(Session.questions).selectinload(SessionQuestion.question))
            .order_by(Session.started_at.desc(), Session.id.desc())
            .offset(offset)
            .limit(limit)
        )
    ).scalars().all()
    items = [_history_item(session) for session in rows]
    log_event("session.history.read", status="success", result_count=len(items), limit=limit, offset=offset)
    return items


@router.get("/{session_id}", response_model=SessionDetailOut)
async def get_session(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionDetailOut:
    session = (
        await db.execute(
            select(Session)
            .where(Session.id == session_id, Session.user_id == current_user.id)
            .options(
                selectinload(Session.questions)
                .selectinload(SessionQuestion.question)
                .selectinload(Question.tag_links)
                .selectinload(QuestionTag.tag),
                selectinload(Session.questions).selectinload(SessionQuestion.messages),
                selectinload(Session.questions).selectinload(SessionQuestion.evaluation_results),
            )
        )
    ).scalar_one_or_none()
    if not session:
        log_event("session.read", status="not_found", session_id=session_id)
        raise HTTPException(status_code=404, detail="Session not found")
    now = _now()
    if _expire_if_needed(session, now):
        await db.commit()
        log_event("session.expire", status="success", session_id=session.id)
    questions = []
    for sq in sorted(session.questions, key=lambda item: item.order_no):
        messages = sorted(sq.messages, key=lambda item: item.id)
        questions.append(
            SessionQuestionOut(
                sq_id=sq.id,
                question=_first_question(sq.question, sq.id),
                status=sq.status,
                started_at=sq.started_at,
                submitted_at=sq.submitted_at,
                scored_at=sq.scored_at,
                followup_count=sq.followup_count,
                final_score=sq.final_score,
                mastery=sq.mastery,
                messages=[MessageOut.model_validate(message) for message in messages],
            )
        )
    log_event("session.read", status="success", session_id=session.id, session_status=session.status)
    return SessionDetailOut(
        session_id=session.id,
        mode=session.mode,
        status=session.status,
        server_now=now,
        started_at=session.started_at,
        deadline_at=session.deadline_at,
        remaining_seconds=_remaining_seconds(session, now),
        current_question_index=session.current_question_index,
        total_questions=session.total_questions,
        max_followups=session.max_followups,
        current_followups=session.current_followups,
        end_reason=session.end_reason,
        questions=questions,
    )


async def _update_retention_tables(
    db: AsyncSession,
    session: Session,
    sq: SessionQuestion,
    score: int,
    mastery: str,
    today: date | None = None,
) -> None:
    review_start = today or date.today()
    question = sq.question
    if mastery in {"weak", "fail"}:
        wrong = await db.get(WrongBook, {"user_id": session.user_id, "question_id": question.id})
        if wrong:
            wrong.last_score = score
            wrong.fail_count += 1
        else:
            wrong = WrongBook(user_id=session.user_id, question_id=question.id, last_score=score, fail_count=1)
            db.add(wrong)
        intervals = [1, 3, 7, 15]
        wrong.next_review = review_start + timedelta(days=intervals[min(wrong.fail_count - 1, len(intervals) - 1)])

    for link in question.tag_links:
        stat = await db.get(UserTagStat, {"user_id": session.user_id, "tag_id": link.tag_id})
        if stat:
            stat.avg_score = ((stat.avg_score * stat.attempts) + score) / (stat.attempts + 1)
            stat.attempts += 1
        else:
            db.add(UserTagStat(user_id=session.user_id, tag_id=link.tag_id, attempts=1, avg_score=score))


def _latest_evaluation(sq: SessionQuestion) -> EvaluationResult | None:
    evaluations = list(getattr(sq, "evaluation_results", []) or [])
    if not evaluations:
        return None
    return sorted(evaluations, key=lambda item: (item.created_at is not None, item.created_at, item.id or 0))[-1]


def _action_items_from_points(missing_points: list[str]) -> list[str]:
    return [f"Review and restate: {point}" for point in missing_points[:5]]


def _evaluation_result_row(session: Session, sq: SessionQuestion, result, model_name: str) -> EvaluationResult:
    assert result.verdict is not None
    missing_points = list(result.missing_points or [])
    return EvaluationResult(
        user_id=session.user_id,
        session_id=session.id,
        sq_id=sq.id,
        question_id=sq.question_id,
        score=result.verdict.score,
        mastery=result.verdict.mastery,
        verdict=result.verdict.feedback,
        strengths=list(result.correct_points or []),
        missing_points=missing_points,
        expression_issues=list(result.wrong_points or []),
        followup_failures=[],
        action_items=_action_items_from_points(missing_points),
        recommended_questions=[],
        raw_model_output=result.as_dict(),
        model_name=model_name,
        prompt_version=PROMPT_VERSION,
    )


def _verdict_payload(sq: SessionQuestion) -> dict:
    evaluation = _latest_evaluation(sq)
    if evaluation:
        raw_verdict = evaluation.raw_model_output.get("verdict") if isinstance(evaluation.raw_model_output, dict) else {}
        raw_verdict = raw_verdict if isinstance(raw_verdict, dict) else {}
        return {
            "feedback": evaluation.verdict,
            "ideal_answer": raw_verdict.get("ideal_answer", sq.question.answer_key),
            "strengths": evaluation.strengths,
            "missing_points": evaluation.missing_points,
            "expression_issues": evaluation.expression_issues,
            "action_items": evaluation.action_items,
            "recommended_questions": evaluation.recommended_questions,
        }

    verdict_message = next(
        (message for message in reversed(sorted(sq.messages, key=lambda item: item.id)) if message.msg_type == "verdict"),
        None,
    )
    verdict = (verdict_message.eval_json or {}).get("verdict", {}) if verdict_message else {}
    eval_json = (verdict_message.eval_json or {}) if verdict_message else {}
    missing_points = list(eval_json.get("missing_points") or [])
    return {
        "feedback": verdict.get("feedback", "本题已完成评估。"),
        "ideal_answer": verdict.get("ideal_answer", sq.question.answer_key),
        "strengths": list(eval_json.get("correct_points") or []),
        "missing_points": missing_points,
        "expression_issues": list(eval_json.get("wrong_points") or []),
        "action_items": _action_items_from_points(missing_points),
        "recommended_questions": [],
    }


def _build_report(session: Session) -> dict:
    finished = [sq for sq in sorted(session.questions, key=lambda item: item.order_no) if sq.final_score is not None]
    overall_score = round(sum(sq.final_score or 0 for sq in finished) / len(finished)) if finished else 0
    tag_scores: dict[str, list[int]] = {}
    questions = []
    for sq in finished:
        details = _verdict_payload(sq)
        tags = [{"id": link.tag.id, "name": link.tag.name, "category": link.tag.category} for link in sq.question.tag_links]
        for tag in tags:
            tag_scores.setdefault(tag["name"], []).append(sq.final_score or 0)
        questions.append(
            {
                "sq_id": sq.id,
                "title": sq.question.title,
                "qtype": sq.question.qtype,
                "difficulty": sq.question.difficulty,
                "score": sq.final_score or 0,
                "mastery": sq.mastery or "fail",
                "feedback": details["feedback"],
                "ideal_answer": details["ideal_answer"],
                "strengths": details["strengths"],
                "missing_points": details["missing_points"],
                "expression_issues": details["expression_issues"],
                "action_items": details["action_items"],
                "recommended_questions": details["recommended_questions"],
                "tags": tags,
            }
        )
    radar = [
        {"tag": tag, "avg_score": round(sum(scores) / len(scores), 2), "attempts": len(scores)}
        for tag, scores in sorted(tag_scores.items())
    ]
    if overall_score >= 80:
        summary = "整体表现扎实，能够覆盖关键要点。建议继续加强复杂场景下的方案取舍。"
    elif overall_score >= 60:
        summary = "基础方向基本正确，但细节、边界条件和表达完整度仍有提升空间。"
    else:
        summary = "核心知识点覆盖不足，建议结合逐题反馈复习后再次进行模拟面试。"
    return {"overall_score": overall_score, "summary": summary, "radar": radar, "questions": questions}


def _report_out(session: Session) -> SessionReportOut:
    report = session.report or _build_report(session)
    return SessionReportOut(
        session_id=session.id,
        mode=session.mode,
        status=session.status,
        overall_score=report.get("overall_score", 0),
        summary=report.get("summary", ""),
        started_at=session.started_at,
        ended_at=session.ended_at,
        radar=[RadarItemOut(**item) for item in report.get("radar", [])],
        questions=[ReportQuestionOut(**item) for item in report.get("questions", [])],
    )


@router.get("/{session_id}/report", response_model=SessionReportOut)
async def get_report(
    session_id: int,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> SessionReportOut:
    session = (
        await db.execute(
            select(Session)
            .where(Session.id == session_id, Session.user_id == current_user.id)
            .options(
                selectinload(Session.questions)
                .selectinload(SessionQuestion.question)
                .selectinload(Question.tag_links)
                .selectinload(QuestionTag.tag),
                selectinload(Session.questions).selectinload(SessionQuestion.messages),
                selectinload(Session.questions).selectinload(SessionQuestion.evaluation_results),
            )
        )
    ).scalar_one_or_none()
    if not session:
        log_event("report.read", status="not_found", session_id=session_id)
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "finished":
        log_event("report.read", status="not_ready", session_id=session_id, session_status=session.status)
        raise HTTPException(status_code=409, detail="Session is not finished")
    log_event("report.read", status="success", session_id=session.id)
    return _report_out(session)


async def _answer_stream(session_id: int, user_id: int, request: AnswerRequest) -> AsyncIterator[str]:
    yield _sse("eval_start", {"sq_id": request.sq_id})
    async with SessionLocal() as db:
        sq = await db.get(
            SessionQuestion,
            request.sq_id,
            options=[
                selectinload(SessionQuestion.question)
                .selectinload(Question.tag_links)
                .selectinload(QuestionTag.tag),
                selectinload(SessionQuestion.question).selectinload(Question.company),
                selectinload(SessionQuestion.question).selectinload(Question.position),
                selectinload(SessionQuestion.messages),
                selectinload(SessionQuestion.session).selectinload(Session.questions),
            ],
        )
        if not sq or sq.session_id != session_id or sq.session.user_id != user_id:
            yield _sse("error", {"message": "Session question not found"})
            return
        try:
            _assert_answerable(sq.session)
        except HTTPException as exc:
            await db.commit()
            yield _sse("error", {"message": str(exc.detail)})
            return
        if sq.status in {"scored", "skipped", "timeout"} or sq.finished_at:
            yield _sse("error", {"message": "Question is already finished"})
            return
        if sq.status != "answering":
            yield _sse("error", {"message": "Question is not active"})
            return

        now = _now()
        sq.answer_text = request.content
        sq.submitted_at = now
        db.add(Message(sq_id=sq.id, role="candidate", content=request.content, msg_type="answer"))
        await db.flush()
        history_rows = (await db.execute(select(Message).where(Message.sq_id == sq.id).order_by(Message.id))).scalars().all()
        history = [ConversationMessage(role=m.role, content=m.content, msg_type=m.msg_type) for m in history_rows]
        depth = sum(1 for m in history_rows if m.role == "interviewer" and m.msg_type in {"followup", "hint"})

        question = sq.question
        engine = InterviewerEngine()
        interview_question = InterviewQuestion(
            title=question.title,
            answer_key=question.answer_key,
            company=question.company.name if question.company else "目标公司",
            position=question.position.name if question.position else "目标岗位",
        )
        prompt_tokens = estimate_prompt_tokens(interview_question, history, request.content, depth)
        provider = provider_from_llm(engine.llm)
        model_name = model_from_llm(engine.llm)
        llm_started_at = perf_counter()
        try:
            result = await engine.evaluate_answer(
                interview_question,
                history,
                request.content,
                depth,
            )
        except Exception as exc:
            if usage_metering_enabled():
                await record_llm_usage(
                    db,
                    user_id=sq.session.user_id,
                    session_id=sq.session.id,
                    feature="scoring",
                    provider=provider,
                    model=model_name,
                    prompt_tokens=prompt_tokens,
                    completion_tokens=0,
                    latency_ms=elapsed_ms(llm_started_at),
                    status="failed",
                    error_type=exc.__class__.__name__,
                )
                await db.commit()
            raise

        llm_call_attempted = bool(getattr(engine, "last_llm_call_attempted", False))
        llm_call_failed = bool(getattr(engine, "last_llm_call_failed", False))
        if llm_call_attempted and usage_metering_enabled():
            await record_llm_usage(
                db,
                user_id=sq.session.user_id,
                session_id=sq.session.id,
                feature=feature_from_result(result) if not llm_call_failed else "scoring",
                provider=provider,
                model=model_name,
                prompt_tokens=prompt_tokens,
                completion_tokens=0 if llm_call_failed else estimate_completion_tokens(result),
                latency_ms=elapsed_ms(llm_started_at),
                status="failed" if llm_call_failed else "success",
                error_type=getattr(engine, "last_llm_error_type", None),
            )

        if result.action == "verdict" and result.verdict:
            content = result.verdict.feedback
            msg_type = "verdict"
            now = _now()
            sq.status = "scored"
            sq.final_score = result.verdict.score
            sq.mastery = result.verdict.mastery
            sq.verdict = result.verdict.as_dict()
            sq.scored_at = now
            sq.finished_at = now
            db.add(_evaluation_result_row(sq.session, sq, result, model_name))
            await _update_retention_tables(db, sq.session, sq, result.verdict.score, result.verdict.mastery)
            next_sq = next(
                (
                    item
                    for item in sorted(sq.session.questions, key=lambda value: value.order_no)
                    if item.order_no > sq.order_no and item.status in {"pending", "answering"}
                ),
                None,
            )
            next_question_payload = None
            if sq.session.mode == "mock" and next_sq:
                next_question = await db.get(
                    Question,
                    next_sq.question_id,
                    options=[selectinload(Question.tag_links).selectinload(QuestionTag.tag)],
                )
                assert next_question is not None
                next_sq.status = "answering"
                next_sq.started_at = now
                sq.session.current_question_id = next_question.id
                sq.session.current_question_index = next_sq.order_no
                sq.session.current_followups = 0
                db.add(Message(sq_id=next_sq.id, role="interviewer", content=next_question.title, msg_type="question"))
                next_question_payload = _first_question(next_question, next_sq.id).model_dump()
            else:
                sq.session.status = "finished"
                sq.session.finished_at = now
                sq.session.ended_at = now
                sq.session.end_reason = "completed"
        else:
            content = result.followup
            msg_type = "hint" if result.action == "followup_hint" else "followup"
            sq.followup_count += 1
            sq.session.current_followups = sq.followup_count

        db.add(Message(sq_id=sq.id, role="interviewer", content=content, msg_type=msg_type, eval_json=result.as_dict()))
        if result.action == "verdict" and (sq.session.mode != "mock" or not next_sq):
            await db.flush()
            refreshed = (
                await db.execute(
                    select(Session)
                    .where(Session.id == sq.session.id, Session.user_id == user_id)
                    .options(
                        selectinload(Session.questions)
                        .selectinload(SessionQuestion.question)
                        .selectinload(Question.tag_links)
                        .selectinload(QuestionTag.tag),
                        selectinload(Session.questions).selectinload(SessionQuestion.messages),
                        selectinload(Session.questions).selectinload(SessionQuestion.evaluation_results),
                    )
                    .execution_options(populate_existing=True)
                )
            ).scalar_one()
            refreshed.report = _build_report(refreshed)
            log_event(
                "report.generate",
                status="success",
                session_id=refreshed.id,
                overall_score=refreshed.report.get("overall_score") if isinstance(refreshed.report, dict) else None,
            )
        await db.commit()

    for char in content:
        yield _sse("token", {"text": char})

    done_payload = {
        "action": result.action,
        "sq_state": "DONE" if result.action == "verdict" else "FOLLOWUP",
        "verdict": result.verdict.as_dict() if result.verdict else None,
        "next_question": next_question_payload if result.action == "verdict" else None,
    }
    yield _sse("done", done_payload)


@router.post("/{session_id}/answer")
async def answer(
    session_id: int,
    request: AnswerRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StreamingResponse:
    row = (
        await db.execute(
            select(Session, SessionQuestion)
            .join(SessionQuestion, SessionQuestion.session_id == Session.id)
            .where(
                Session.id == session_id,
                Session.user_id == current_user.id,
                SessionQuestion.id == request.sq_id,
            )
            .options(selectinload(Session.questions))
        )
    )
    result = row.first()
    if result is None:
        log_event("answer.submit", status="not_found", session_id=session_id, sq_id=request.sq_id)
        raise HTTPException(status_code=404, detail="Session question not found")
    session, sq = result
    try:
        _assert_answerable(session)
    except HTTPException:
        await db.commit()
        log_event("answer.submit", status="not_answerable", session_id=session_id, sq_id=request.sq_id, session_status=session.status)
        raise
    if sq.status in {"scored", "skipped", "timeout"} or sq.finished_at:
        log_event("answer.submit", status="conflict", session_id=session_id, sq_id=request.sq_id, question_status=sq.status)
        raise HTTPException(status_code=409, detail="Question is already finished")
    if sq.status != "answering":
        log_event("answer.submit", status="conflict", session_id=session_id, sq_id=request.sq_id, question_status=sq.status)
        raise HTTPException(status_code=409, detail="Question is not active")
    log_event("answer.submit", status="accepted", session_id=session_id, sq_id=request.sq_id)
    return StreamingResponse(_answer_stream(session_id, current_user.id, request), media_type="text/event-stream")
