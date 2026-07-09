from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.metrics import record_memory_created, record_memory_refresh
from app.models import AgentMemory, AuditEvent, Question, QuestionTag, Session, SessionQuestion, Tag, UserTagStat, WrongBook
from app.observability import get_request_id, log_event


ACTIVE = "active"
ARCHIVED = "archived"
MEMORY_TYPES = {"weakness", "strength", "preference", "training_goal", "recurring_issue", "recommendation"}
MEMORY_STATUSES = {ACTIVE, ARCHIVED}


@dataclass
class MemoryRefreshStats:
    created: int = 0
    updated: int = 0


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _score(value: Decimal | float | int | None) -> float:
    return float(value or 0)


def _tag_payload(tag_id: int | None, tag: str | None, category: str | None = None) -> dict[str, Any]:
    return {"tag_id": tag_id, "tag": tag or "unknown", "category": category}


def _primary_tag_key(tags: list[dict[str, Any]]) -> str:
    if not tags:
        return "unknown"
    first = tags[0]
    if first.get("tag_id") is not None:
        return f"id:{first['tag_id']}"
    return f"name:{str(first.get('tag') or 'unknown').lower()}"


def _evidence_key(evidence: dict[str, Any]) -> tuple[Any, ...]:
    return (
        evidence.get("source_type"),
        evidence.get("session_id"),
        evidence.get("report_id"),
        evidence.get("question_id"),
        evidence.get("tag_id"),
        evidence.get("rubric_version_id"),
    )


def _append_evidence(existing: list[dict[str, Any]], evidence: dict[str, Any]) -> list[dict[str, Any]]:
    evidence_items = list(existing or [])
    if _evidence_key(evidence) not in {_evidence_key(item) for item in evidence_items}:
        evidence_items.append(evidence)
    return evidence_items[-10:]


def _add_audit_event(
    db: AsyncSession,
    *,
    user_id: int,
    action: str,
    memory: AgentMemory,
    status: str = "success",
    reason: str | None = None,
) -> None:
    db.add(
        AuditEvent(
            actor_user_id=user_id,
            actor_role="user",
            action=action,
            resource_type="agent_memory",
            resource_id=str(memory.id) if memory.id is not None else None,
            target_user_id=user_id,
            request_id=get_request_id(),
            status=status,
            reason=reason,
            metadata_json={
                "memory_type": memory.memory_type,
                "status": memory.status,
                "source_type": memory.source_type,
                "tag_count": len(memory.tags_json or []),
            },
        )
    )


async def upsert_user_memory(
    db: AsyncSession,
    *,
    user_id: int,
    memory_type: str,
    title: str,
    summary: str,
    tags: list[dict[str, Any]],
    evidence: dict[str, Any],
    source_type: str,
    source_id: int | None = None,
    now: datetime | None = None,
) -> tuple[AgentMemory, bool]:
    if memory_type not in MEMORY_TYPES:
        raise ValueError(f"Unsupported memory_type: {memory_type}")
    current = now or _now()
    primary_key = _primary_tag_key(tags)
    rows = (
        await db.execute(
            select(AgentMemory).where(
                AgentMemory.user_id == user_id,
                AgentMemory.memory_type == memory_type,
                AgentMemory.status == ACTIVE,
            )
        )
    ).scalars()
    for memory in rows:
        if _primary_tag_key(list(memory.tags_json or [])) == primary_key:
            memory.title = title
            memory.summary = summary
            memory.tags_json = tags
            memory.evidence_json = _append_evidence(list(memory.evidence_json or []), evidence)
            memory.confidence = min(Decimal("0.95"), Decimal(str(memory.confidence or Decimal("0.50"))) + Decimal("0.10"))
            memory.source_type = source_type
            memory.source_id = source_id
            memory.last_seen_at = current
            memory.updated_at = current
            await db.flush()
            _add_audit_event(db, user_id=user_id, action="memory_updated", memory=memory)
            return memory, False

    memory = AgentMemory(
        user_id=user_id,
        memory_type=memory_type,
        title=title,
        summary=summary,
        tags_json=tags,
        evidence_json=[evidence],
        confidence=Decimal("0.50"),
        status=ACTIVE,
        source_type=source_type,
        source_id=source_id,
        first_seen_at=current,
        last_seen_at=current,
        created_at=current,
        updated_at=current,
    )
    db.add(memory)
    await db.flush()
    _add_audit_event(db, user_id=user_id, action="memory_created", memory=memory)
    record_memory_created(memory_type)
    return memory, True


async def _generate_from_report(db: AsyncSession, session: Session, stats: MemoryRefreshStats) -> None:
    report = session.report if isinstance(session.report, dict) else {}
    questions = report.get("questions") if isinstance(report, dict) else []
    if not isinstance(questions, list):
        return

    for item in questions:
        if not isinstance(item, dict):
            continue
        tags = item.get("tags") if isinstance(item.get("tags"), list) else []
        score = int(item.get("score") or 0)
        question_id = item.get("question_id") or _question_id_from_sq(session, item.get("sq_id"))
        rubric_version_id = item.get("rubric_version_id")
        for raw_tag in tags:
            tag_payload = _tag_payload(raw_tag.get("id"), raw_tag.get("name"), raw_tag.get("category")) if isinstance(raw_tag, dict) else _tag_payload(None, str(raw_tag))
            evidence = {
                "source_type": "report",
                "report_id": session.id,
                "session_id": session.id,
                "question_id": question_id,
                "tag_id": tag_payload["tag_id"],
                "tag": tag_payload["tag"],
                "score": score,
                "rubric_version_id": rubric_version_id,
            }
            if score < 70:
                _, created = await upsert_user_memory(
                    db,
                    user_id=session.user_id,
                    memory_type="weakness",
                    title=f"{tag_payload['tag']} needs reinforcement",
                    summary=f"Recent interview scoring shows {tag_payload['tag']} is a priority weakness.",
                    tags=[tag_payload],
                    evidence=evidence,
                    source_type="report",
                    source_id=session.id,
                )
                stats.created += 1 if created else 0
                stats.updated += 0 if created else 1
            elif score >= 85:
                _, created = await upsert_user_memory(
                    db,
                    user_id=session.user_id,
                    memory_type="strength",
                    title=f"{tag_payload['tag']} is a stable strength",
                    summary=f"Recent interview scoring shows {tag_payload['tag']} is a comparatively strong area.",
                    tags=[tag_payload],
                    evidence=evidence,
                    source_type="report",
                    source_id=session.id,
                )
                stats.created += 1 if created else 0
                stats.updated += 0 if created else 1
            if score < 80:
                _, created = await upsert_user_memory(
                    db,
                    user_id=session.user_id,
                    memory_type="recommendation",
                    title=f"Next practice should include {tag_payload['tag']}",
                    summary=f"Continue targeted practice for {tag_payload['tag']} before the next mock interview.",
                    tags=[tag_payload],
                    evidence=evidence,
                    source_type="report",
                    source_id=session.id,
                )
                stats.created += 1 if created else 0
                stats.updated += 0 if created else 1


def _question_id_from_sq(session: Session, sq_id: Any) -> int | None:
    for sq in session.questions or []:
        if sq.id == sq_id:
            return sq.question_id
    return None


async def _generate_from_user_tag_stats(db: AsyncSession, user_id: int, stats: MemoryRefreshStats) -> None:
    rows = (
        await db.execute(
            select(UserTagStat, Tag)
            .join(Tag, Tag.id == UserTagStat.tag_id)
            .where(UserTagStat.user_id == user_id, UserTagStat.attempts >= 2)
        )
    ).all()
    for stat, tag in rows:
        avg_score = _score(stat.avg_score)
        if avg_score >= 85 or avg_score < 70:
            memory_type = "strength" if avg_score >= 85 else "weakness"
            tag_payload = _tag_payload(tag.id, tag.name, tag.category)
            _, created = await upsert_user_memory(
                db,
                user_id=user_id,
                memory_type=memory_type,
                title=f"{tag.name} {'is stable' if memory_type == 'strength' else 'needs reinforcement'}",
                summary=f"Long-term tag statistics show {tag.name} average score is {avg_score:.0f} across {stat.attempts} attempts.",
                tags=[tag_payload],
                evidence={
                    "source_type": "ability_profile",
                    "tag_id": tag.id,
                    "tag": tag.name,
                    "avg_score": avg_score,
                    "attempts": stat.attempts,
                },
                source_type="ability_profile",
                source_id=tag.id,
            )
            stats.created += 1 if created else 0
            stats.updated += 0 if created else 1


async def _generate_from_wrong_book(db: AsyncSession, user_id: int, stats: MemoryRefreshStats) -> None:
    rows = (
        await db.execute(
            select(WrongBook, Question, Tag)
            .join(Question, Question.id == WrongBook.question_id)
            .join(QuestionTag, QuestionTag.question_id == Question.id)
            .join(Tag, Tag.id == QuestionTag.tag_id)
            .where(WrongBook.user_id == user_id, WrongBook.fail_count >= 2)
        )
    ).all()
    for wrong, question, tag in rows:
        tag_payload = _tag_payload(tag.id, tag.name, tag.category)
        _, created = await upsert_user_memory(
            db,
            user_id=user_id,
            memory_type="recurring_issue",
            title=f"{tag.name} appears repeatedly in wrong-book reviews",
            summary=f"Wrong-book history shows repeated misses around {tag.name}.",
            tags=[tag_payload],
            evidence={
                "source_type": "wrong_book",
                "question_id": question.id,
                "tag_id": tag.id,
                "tag": tag.name,
                "score": wrong.last_score,
                "fail_count": wrong.fail_count,
            },
            source_type="wrong_book",
            source_id=question.id,
        )
        stats.created += 1 if created else 0
        stats.updated += 0 if created else 1


async def refresh_memories_from_session_report(
    db: AsyncSession,
    *,
    user_id: int,
    session_id: int,
    trigger: str = "report",
) -> MemoryRefreshStats:
    session = (
        await db.execute(
            select(Session)
            .where(Session.id == session_id, Session.user_id == user_id)
            .options(
                selectinload(Session.questions).selectinload(SessionQuestion.question),
            )
        )
    ).scalar_one_or_none()
    if not session or session.status != "finished" or not isinstance(session.report, dict):
        stats = MemoryRefreshStats()
        record_memory_refresh("skipped", trigger)
        return stats
    stats = MemoryRefreshStats()
    await _generate_from_report(db, session, stats)
    await _generate_from_user_tag_stats(db, user_id, stats)
    await _generate_from_wrong_book(db, user_id, stats)
    await db.commit()
    record_memory_refresh("success", trigger)
    log_event("memory.refresh", status="success", trigger=trigger, created=stats.created, updated=stats.updated)
    return stats


async def refresh_user_memories(db: AsyncSession, *, user_id: int, trigger: str = "manual") -> MemoryRefreshStats:
    stats = MemoryRefreshStats()
    latest_sessions = (
        await db.execute(
            select(Session)
            .where(Session.user_id == user_id, Session.status == "finished", Session.report.is_not(None))
            .order_by(Session.finished_at.desc().nullslast(), Session.started_at.desc())
            .limit(5)
            .options(selectinload(Session.questions))
        )
    ).scalars()
    for session in latest_sessions:
        await _generate_from_report(db, session, stats)
    await _generate_from_user_tag_stats(db, user_id, stats)
    await _generate_from_wrong_book(db, user_id, stats)
    await db.commit()
    record_memory_refresh("success", trigger)
    log_event("memory.refresh", status="success", trigger=trigger, created=stats.created, updated=stats.updated)
    return stats


async def list_user_memories(
    db: AsyncSession,
    *,
    user_id: int,
    memory_type: str | None = None,
    status: str = ACTIVE,
    tag: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> tuple[list[AgentMemory], int]:
    conditions = [AgentMemory.user_id == user_id]
    if memory_type:
        conditions.append(AgentMemory.memory_type == memory_type)
    if status:
        conditions.append(AgentMemory.status == status)
    rows = (
        await db.execute(
            select(AgentMemory)
            .where(*conditions)
            .order_by(AgentMemory.last_seen_at.desc(), AgentMemory.id.desc())
        )
    ).scalars().all()
    if tag:
        needle = tag.lower()
        rows = [
            memory
            for memory in rows
            if any(needle in str(item.get("tag", "")).lower() for item in list(memory.tags_json or []))
        ]
    total = len(rows)
    return rows[offset : offset + limit], total


async def archive_user_memory(db: AsyncSession, *, user_id: int, memory_id: int) -> AgentMemory | None:
    memory = (
        await db.execute(
            select(AgentMemory).where(AgentMemory.id == memory_id, AgentMemory.user_id == user_id)
        )
    ).scalar_one_or_none()
    if not memory:
        return None
    memory.status = ARCHIVED
    memory.updated_at = _now()
    await db.flush()
    _add_audit_event(db, user_id=user_id, action="memory_archived", memory=memory)
    await db.commit()
    await db.refresh(memory)
    return memory


async def active_memory_count(db: AsyncSession, user_id: int) -> int:
    return int(
        await db.scalar(select(func.count()).select_from(AgentMemory).where(AgentMemory.user_id == user_id, AgentMemory.status == ACTIVE))
        or 0
    )
