from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Question, ScoringRubric, ScoringRubricVersion


RUBRIC_STATUS_DRAFT = "draft"
RUBRIC_STATUS_PUBLISHED = "published"
RUBRIC_STATUS_ARCHIVED = "archived"
RUBRIC_STATUSES = {RUBRIC_STATUS_DRAFT, RUBRIC_STATUS_PUBLISHED, RUBRIC_STATUS_ARCHIVED}
SYSTEM_DEFAULT_RUBRIC_NAME = "system_default"
SYSTEM_DEFAULT_RUBRIC_VERSION = "v1"

SYSTEM_DEFAULT_DIMENSIONS: list[dict[str, Any]] = [
    {"key": "correctness", "name": "正确性", "weight": 40, "description": "核心概念、事实和结论是否准确。"},
    {"key": "completeness", "name": "完整性", "weight": 30, "description": "是否覆盖关键要点、边界条件和取舍。"},
    {"key": "expression", "name": "表达结构", "weight": 20, "description": "回答是否结构清晰、层次明确。"},
    {"key": "depth", "name": "工程深度", "weight": 10, "description": "是否能结合场景、风险和落地方案展开。"},
]

SYSTEM_DEFAULT_PROMPT_TEMPLATE = (
    "按照正确性、完整性、表达结构和工程深度四个维度对候选人回答进行评分，"
    "输出 0-100 分、掌握度、反馈、优点、缺失点和参考答案。"
)


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


async def ensure_system_default_rubric_version(db: AsyncSession) -> ScoringRubricVersion:
    rubric = (
        await db.execute(select(ScoringRubric).where(ScoringRubric.name == SYSTEM_DEFAULT_RUBRIC_NAME))
    ).scalar_one_or_none()
    current_time = now_utc()
    if rubric is None:
        rubric = ScoringRubric(
            name=SYSTEM_DEFAULT_RUBRIC_NAME,
            description="System default scoring rubric for interview answer evaluation.",
            status=RUBRIC_STATUS_PUBLISHED,
            created_at=current_time,
            updated_at=current_time,
        )
        db.add(rubric)
        await db.flush()

    version = (
        await db.execute(
            select(ScoringRubricVersion).where(
                ScoringRubricVersion.rubric_id == rubric.id,
                ScoringRubricVersion.version == SYSTEM_DEFAULT_RUBRIC_VERSION,
            )
        )
    ).scalar_one_or_none()
    if version is None:
        version = ScoringRubricVersion(
            rubric_id=rubric.id,
            version=SYSTEM_DEFAULT_RUBRIC_VERSION,
            dimensions_json=SYSTEM_DEFAULT_DIMENSIONS,
            prompt_template=SYSTEM_DEFAULT_PROMPT_TEMPLATE,
            scoring_scale="0-100",
            status=RUBRIC_STATUS_PUBLISHED,
            created_at=current_time,
            published_at=current_time,
        )
        db.add(version)
        await db.flush()
    return version


async def select_scoring_rubric_version(db: AsyncSession, question: Question) -> ScoringRubricVersion:
    if question.default_rubric_version_id:
        version = await db.get(ScoringRubricVersion, question.default_rubric_version_id)
        if version and version.status == RUBRIC_STATUS_PUBLISHED:
            return version
    return await ensure_system_default_rubric_version(db)
