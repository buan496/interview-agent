from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.db import SessionLocal
from app.models import Company, Position, Question, QuestionTag, Tag


async def _get_or_create_company(db, item: dict[str, Any]) -> Company:
    name = item["company"]
    company = (await db.execute(select(Company).where(Company.name == name))).scalar_one_or_none()
    if company:
        return company
    company = Company(name=name, name_en=item.get("company_en"), region=item.get("region", "CN"), tier=item.get("tier", 1))
    db.add(company)
    await db.flush()
    return company


async def _get_or_create_position(db, name: str) -> Position:
    position = (await db.execute(select(Position).where(Position.name == name))).scalar_one_or_none()
    if position:
        return position
    position = Position(name=name)
    db.add(position)
    await db.flush()
    return position


async def _get_or_create_tag(db, name: str, category: str | None = None) -> Tag:
    tag = (await db.execute(select(Tag).where(Tag.name == name))).scalar_one_or_none()
    if tag:
        return tag
    tag = Tag(name=name, category=category)
    db.add(tag)
    await db.flush()
    return tag


async def load_seed(path: Path) -> int:
    count = 0
    async with SessionLocal() as db:
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            item = json.loads(line)
            exists = (await db.execute(select(Question).where(Question.title == item["title"]))).scalar_one_or_none()
            if exists:
                continue
            company = await _get_or_create_company(db, item)
            position = await _get_or_create_position(db, item["position"])
            question = Question(
                title=item["title"],
                body=item.get("body"),
                answer_key=item["answer_key"],
                difficulty=item.get("difficulty", 3),
                qtype=item["qtype"],
                source_type=item.get("source_type", "seed"),
                source_note=item.get("source_note"),
                company_id=company.id,
                position_id=position.id,
                status=item.get("status", "active"),
            )
            db.add(question)
            await db.flush()
            for tag_item in item.get("tags", []):
                if isinstance(tag_item, dict):
                    tag = await _get_or_create_tag(db, tag_item["name"], tag_item.get("category"))
                else:
                    tag = await _get_or_create_tag(db, str(tag_item))
                db.add(QuestionTag(question_id=question.id, tag_id=tag.id))
            count += 1
        await db.commit()
    return count


def main() -> None:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).with_name("questions_seed.jsonl")
    loaded = asyncio.run(load_seed(path))
    print(f"loaded {loaded} questions")


if __name__ == "__main__":
    main()

