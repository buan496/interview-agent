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
from app.db import SessionLocal, get_db
from app.models import Message, Question, QuestionTag, Session, SessionQuestion, Tag, User, UserTagStat, WrongBook
from app.schemas import (
    AnswerRequest,
    CreateSessionOut,
    CreateSessionRequest,
    FirstQuestionOut,
    MessageOut,
    SessionDetailOut,
    SessionQuestionOut,
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


async def _select_question(db: AsyncSession, request: CreateSessionRequest) -> Question | None:
    stmt = select(Question).where(Question.status == "active")
    if request.company_id:
        stmt = stmt.where(Question.company_id == request.company_id)
    if request.position_id:
        stmt = stmt.where(Question.position_id == request.position_id)
    if request.difficulty:
        stmt = stmt.where(Question.difficulty == request.difficulty)
    if request.tag_ids:
        stmt = stmt.join(QuestionTag).where(QuestionTag.tag_id.in_(request.tag_ids)).distinct()
    stmt = stmt.options(
        selectinload(Question.company),
        selectinload(Question.position),
        selectinload(Question.tag_links).selectinload(QuestionTag.tag),
    ).order_by(func.random()).limit(1)
    return (await db.execute(stmt)).scalar_one_or_none()


@router.post("", response_model=CreateSessionOut)
async def create_session(request: CreateSessionRequest, db: AsyncSession = Depends(get_db)) -> CreateSessionOut:
    if request.mode != "single":
        raise HTTPException(status_code=400, detail="MVP currently supports single mode")

    question = await _select_question(db, request)
    if not question:
        raise HTTPException(status_code=404, detail="No active question matched filters")

    user = await _demo_user(db)
    session = Session(
        user_id=user.id,
        mode=request.mode,
        company_id=request.company_id or question.company_id,
        position_id=request.position_id or question.position_id,
    )
    db.add(session)
    await db.flush()

    sq = SessionQuestion(session_id=session.id, question_id=question.id, order_no=1)
    db.add(sq)
    question.ask_count += 1
    await db.flush()

    db.add(Message(sq_id=sq.id, role="interviewer", content=question.title, msg_type="question"))
    await db.commit()
    return CreateSessionOut(session_id=session.id, first_question=_first_question(question, sq.id))


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
                selectinload(SessionQuestion.session),
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
            sq.session.status = "finished"
            await _update_retention_tables(db, sq.session, sq, result.verdict.score, result.verdict.mastery)
        else:
            content = result.followup
            msg_type = "hint" if result.action == "followup_hint" else "followup"

        db.add(Message(sq_id=sq.id, role="interviewer", content=content, msg_type=msg_type, eval_json=result.as_dict()))
        await db.commit()

    for char in content:
        yield _sse("token", {"text": char})

    done_payload = {
        "action": result.action,
        "sq_state": "DONE" if result.action == "verdict" else "FOLLOWUP",
        "verdict": result.verdict.as_dict() if result.verdict else None,
        "next_question": None,
    }
    yield _sse("done", done_payload)


@router.post("/{session_id}/answer")
async def answer(session_id: int, request: AnswerRequest) -> StreamingResponse:
    return StreamingResponse(_answer_stream(session_id, request), media_type="text/event-stream")

