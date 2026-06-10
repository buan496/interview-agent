from __future__ import annotations

import json
from collections.abc import AsyncIterator
from datetime import date, timedelta

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.interviewer import ConversationMessage, InterviewerEngine, InterviewQuestion
from app.core.scheduler import target_question_count, target_type_counts
from app.db import SessionLocal, get_db
from app.models import Message, Question, QuestionTag, Session, SessionQuestion, Tag, User, UserTagStat, WrongBook
from app.schemas import (
    AnswerRequest,
    CreateSessionOut,
    CreateSessionRequest,
    FirstQuestionOut,
    MessageOut,
    RadarItemOut,
    ReportQuestionOut,
    SessionDetailOut,
    SessionQuestionOut,
    SessionReportOut,
    TagOut,
)


router = APIRouter(prefix="/sessions", tags=["sessions"])


def _sse(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _demo_user(db: AsyncSession) -> User:
    user = (await db.execute(select(User).where(User.phone == "demo"))).scalar_one_or_none()
    if user:
        return user
    user = User(phone="demo", nickname="练习用户")
    db.add(user)
    await db.flush()
    return user


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
async def create_session(request: CreateSessionRequest, db: AsyncSession = Depends(get_db)) -> CreateSessionOut:
    questions = (
        await _select_mock_questions(db, request)
        if request.mode == "mock"
        else [question] if (question := await _select_question(db, request)) else []
    )
    if not questions:
        raise HTTPException(status_code=404, detail="No active question matched filters")

    user = await _demo_user(db)
    session = Session(
        user_id=user.id,
        mode=request.mode,
        company_id=request.company_id or questions[0].company_id,
        position_id=request.position_id or questions[0].position_id,
    )
    db.add(session)
    await db.flush()

    first_sq: SessionQuestion | None = None
    for order_no, question in enumerate(questions, start=1):
        sq = SessionQuestion(session_id=session.id, question_id=question.id, order_no=order_no)
        db.add(sq)
        question.ask_count += 1
        await db.flush()
        if first_sq is None:
            first_sq = sq

    assert first_sq is not None
    db.add(Message(sq_id=first_sq.id, role="interviewer", content=questions[0].title, msg_type="question"))
    await db.commit()
    return CreateSessionOut(session_id=session.id, first_question=_first_question(questions[0], first_sq.id))


@router.get("/{session_id}", response_model=SessionDetailOut)
async def get_session(session_id: int, db: AsyncSession = Depends(get_db)) -> SessionDetailOut:
    session = await db.get(
        Session,
        session_id,
        options=[
            selectinload(Session.questions)
            .selectinload(SessionQuestion.question)
            .selectinload(Question.tag_links)
            .selectinload(QuestionTag.tag),
            selectinload(Session.questions).selectinload(SessionQuestion.messages),
        ],
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    questions = []
    for sq in sorted(session.questions, key=lambda item: item.order_no):
        messages = sorted(sq.messages, key=lambda item: item.id)
        questions.append(
            SessionQuestionOut(
                sq_id=sq.id,
                question=_first_question(sq.question, sq.id),
                final_score=sq.final_score,
                mastery=sq.mastery,
                messages=[MessageOut.model_validate(message) for message in messages],
            )
        )
    return SessionDetailOut(session_id=session.id, mode=session.mode, status=session.status, questions=questions)


async def _update_retention_tables(db: AsyncSession, session: Session, sq: SessionQuestion, score: int, mastery: str) -> None:
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
        wrong.next_review = date.today() + timedelta(days=intervals[min(wrong.fail_count - 1, len(intervals) - 1)])

    for link in question.tag_links:
        stat = await db.get(UserTagStat, {"user_id": session.user_id, "tag_id": link.tag_id})
        if stat:
            stat.avg_score = ((stat.avg_score * stat.attempts) + score) / (stat.attempts + 1)
            stat.attempts += 1
        else:
            db.add(UserTagStat(user_id=session.user_id, tag_id=link.tag_id, attempts=1, avg_score=score))


def _verdict_payload(sq: SessionQuestion) -> dict:
    verdict_message = next(
        (message for message in reversed(sorted(sq.messages, key=lambda item: item.id)) if message.msg_type == "verdict"),
        None,
    )
    verdict = (verdict_message.eval_json or {}).get("verdict", {}) if verdict_message else {}
    return {
        "feedback": verdict.get("feedback", "本题已完成评估。"),
        "ideal_answer": verdict.get("ideal_answer", sq.question.answer_key),
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
async def get_report(session_id: int, db: AsyncSession = Depends(get_db)) -> SessionReportOut:
    session = await db.get(
        Session,
        session_id,
        options=[
            selectinload(Session.questions)
            .selectinload(SessionQuestion.question)
            .selectinload(Question.tag_links)
            .selectinload(QuestionTag.tag),
            selectinload(Session.questions).selectinload(SessionQuestion.messages),
        ],
    )
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    if session.status != "finished":
        raise HTTPException(status_code=409, detail="Session is not finished")
    return _report_out(session)


async def _answer_stream(session_id: int, request: AnswerRequest) -> AsyncIterator[str]:
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
        if not sq or sq.session_id != session_id:
            yield _sse("error", {"message": "Session question not found"})
            return
        if sq.finished_at:
            yield _sse("error", {"message": "Question is already finished"})
            return

        db.add(Message(sq_id=sq.id, role="candidate", content=request.content, msg_type="answer"))
        await db.flush()
        history_rows = (await db.execute(select(Message).where(Message.sq_id == sq.id).order_by(Message.id))).scalars().all()
        history = [ConversationMessage(role=m.role, content=m.content, msg_type=m.msg_type) for m in history_rows]
        depth = sum(1 for m in history_rows if m.role == "interviewer" and m.msg_type in {"followup", "hint"})

        question = sq.question
        engine = InterviewerEngine()
        result = await engine.evaluate_answer(
            InterviewQuestion(
                title=question.title,
                answer_key=question.answer_key,
                company=question.company.name if question.company else "目标公司",
                position=question.position.name if question.position else "目标岗位",
            ),
            history,
            request.content,
            depth,
        )

        if result.action == "verdict" and result.verdict:
            content = result.verdict.feedback
            msg_type = "verdict"
            sq.final_score = result.verdict.score
            sq.mastery = result.verdict.mastery
            sq.finished_at = func.now()
            await _update_retention_tables(db, sq.session, sq, result.verdict.score, result.verdict.mastery)
            next_sq = next(
                (
                    item
                    for item in sorted(sq.session.questions, key=lambda value: value.order_no)
                    if item.order_no > sq.order_no and item.finished_at is None
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
                db.add(Message(sq_id=next_sq.id, role="interviewer", content=next_question.title, msg_type="question"))
                next_question_payload = _first_question(next_question, next_sq.id).model_dump()
            else:
                sq.session.status = "finished"
                sq.session.ended_at = func.now()
        else:
            content = result.followup
            msg_type = "hint" if result.action == "followup_hint" else "followup"

        db.add(Message(sq_id=sq.id, role="interviewer", content=content, msg_type=msg_type, eval_json=result.as_dict()))
        if result.action == "verdict" and (sq.session.mode != "mock" or not next_sq):
            await db.flush()
            refreshed = (
                await db.execute(
                    select(Session)
                    .where(Session.id == sq.session.id)
                    .options(
                        selectinload(Session.questions)
                        .selectinload(SessionQuestion.question)
                        .selectinload(Question.tag_links)
                        .selectinload(QuestionTag.tag),
                        selectinload(Session.questions).selectinload(SessionQuestion.messages),
                    )
                    .execution_options(populate_existing=True)
                )
            ).scalar_one()
            refreshed.report = _build_report(refreshed)
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
async def answer(session_id: int, request: AnswerRequest) -> StreamingResponse:
    return StreamingResponse(_answer_stream(session_id, request), media_type="text/event-stream")
