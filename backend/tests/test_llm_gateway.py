from __future__ import annotations

import unittest
from unittest.mock import patch

from sqlalchemy import select
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from app.api.sessions import _record_engine_llm_usage
from app.core.interviewer import EvaluationResult, Verdict
from app.core.llm import ChatMessage, LLMResponseError
from app.llm_gateway import LLMAttempt, LLMGateway, ModelRoute, parse_model_route
from app.models import Base, LLMUsageRecord, Session, User
from app.settings import Settings


class _FakeProvider:
    def __init__(self, model: str, _settings: Settings) -> None:
        self.model = model

    async def json_chat(self, _messages):
        if "fail" in self.model:
            raise LLMResponseError("planned provider failure")
        return {
            "coverage": 0.9,
            "correct_points": ["ok"],
            "missing_points": [],
            "wrong_points": [],
            "action": "verdict",
            "verdict": {"score": 90, "mastery": "pass", "feedback": "ok", "ideal_answer": "ok"},
        }


def _settings(**overrides) -> Settings:
    values = {
        "llm_provider": "mock",
        "llm_default_provider": "mock",
        "llm_default_model": "default-model",
        "llm_fallback_provider": "mock",
        "llm_fallback_model": "fallback-model",
        "llm_fallback_enabled": True,
        "llm_max_retries": 1,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


class LLMGatewayTest(unittest.IsolatedAsyncioTestCase):
    async def test_feature_route_selects_configured_model(self) -> None:
        settings = _settings(llm_route_interview_scoring="mock/scoring-model")
        gateway = LLMGateway(settings=settings)

        with patch("app.llm_gateway.build_provider", side_effect=lambda route, settings: _FakeProvider(route.model, settings)):
            response = await gateway.call_json(
                feature="interview_scoring",
                messages=[ChatMessage(role="system", content="private prompt text")],
            )

        self.assertEqual(response.provider, "mock")
        self.assertEqual(response.model, "scoring-model")
        self.assertEqual([attempt.status for attempt in gateway.last_attempts], ["success"])
        self.assertFalse(response.fallback_used)

    async def test_unconfigured_route_uses_default_model(self) -> None:
        gateway = LLMGateway(settings=_settings())

        with patch("app.llm_gateway.build_provider", side_effect=lambda route, settings: _FakeProvider(route.model, settings)):
            response = await gateway.call_json(
                feature="memory_refresh",
                messages=[ChatMessage(role="system", content="memory refresh")],
            )

        self.assertEqual(response.model, "default-model")

    async def test_primary_failure_uses_fallback_and_records_attempts(self) -> None:
        settings = _settings(llm_route_interview_scoring="mock/primary-fail")
        gateway = LLMGateway(settings=settings)

        with patch("app.llm_gateway.build_provider", side_effect=lambda route, settings: _FakeProvider(route.model, settings)):
            response = await gateway.call_json(
                feature="interview_scoring",
                messages=[ChatMessage(role="system", content="answer text is not persisted")],
            )

        self.assertTrue(response.fallback_used)
        self.assertEqual(response.model, "fallback-model")
        self.assertEqual([(attempt.model, attempt.status, attempt.fallback) for attempt in gateway.last_attempts], [
            ("primary-fail", "failed", False),
            ("fallback-model", "success", True),
        ])

    async def test_fallback_failure_returns_standard_error(self) -> None:
        settings = _settings(llm_route_interview_scoring="mock/primary-fail", llm_fallback_model="fallback-fail")
        gateway = LLMGateway(settings=settings)

        with patch("app.llm_gateway.build_provider", side_effect=lambda route, settings: _FakeProvider(route.model, settings)):
            with self.assertRaises(LLMResponseError):
                await gateway.call_json(
                    feature="interview_scoring",
                    messages=[ChatMessage(role="system", content="prompt body")],
                )

        self.assertEqual([attempt.status for attempt in gateway.last_attempts], ["failed", "failed"])

    def test_parse_model_route_supports_provider_model_and_default_provider(self) -> None:
        route = parse_model_route("deepseek/deepseek-chat", ModelRoute(provider="mock", model="default"))
        self.assertEqual(route.provider, "deepseek")
        self.assertEqual(route.model, "deepseek-chat")

    async def test_session_usage_records_gateway_primary_and_fallback_attempts(self) -> None:
        engine = create_async_engine(
            "sqlite+aiosqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        sessionmaker = async_sessionmaker(engine, expire_on_commit=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        async with sessionmaker() as db:
            db.add(User(id=1, phone="18819990000"))
            db.add(Session(id=101, user_id=1, mode="single", status="ongoing", total_questions=1))
            await db.flush()
            fake_engine = type(
                "FakeGatewayEngine",
                (),
                {
                    "last_llm_attempts": [
                        LLMAttempt(
                            provider="deepseek",
                            model="deepseek-chat",
                            feature="interview_scoring",
                            status="failed",
                            latency_ms=111,
                            error_type="LLMConfigurationError",
                        ),
                        LLMAttempt(
                            provider="mock",
                            model="local-fallback",
                            feature="interview_scoring",
                            status="success",
                            latency_ms=8,
                            fallback=True,
                        ),
                    ],
                    "last_llm_call_failed": False,
                    "last_llm_error_type": None,
                    "llm": object(),
                },
            )()
            result = EvaluationResult(
                coverage=0.9,
                action="verdict",
                verdict=Verdict(score=90, mastery="pass", feedback="short feedback", ideal_answer="reference"),
            )

            await _record_engine_llm_usage(
                db,
                engine=fake_engine,
                user_id=1,
                session_id=101,
                prompt_tokens=100,
                result=result,
                fallback_latency_ms=200,
            )
            await db.commit()

            records = (await db.execute(select(LLMUsageRecord).order_by(LLMUsageRecord.id))).scalars().all()

        await engine.dispose()

        self.assertEqual([(item.provider, item.model, item.feature, item.status) for item in records], [
            ("deepseek", "deepseek-chat", "interview_scoring", "failed"),
            ("mock", "local-fallback", "interview_scoring", "success"),
        ])
        self.assertEqual(records[0].completion_tokens, 0)
        self.assertGreater(records[1].completion_tokens, 0)
        sensitive_columns = {"prompt", "prompt_text", "completion", "completion_text", "answer", "answer_text"}
        self.assertTrue(sensitive_columns.isdisjoint(LLMUsageRecord.__table__.columns.keys()))


if __name__ == "__main__":
    unittest.main()
