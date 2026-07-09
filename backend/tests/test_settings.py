from __future__ import annotations

import json
import unittest

from pydantic import ValidationError

from app.settings import ConfigValidationError, DEFAULT_DEV_CODE, DEFAULT_JWT_SECRET, Settings


def _production_settings(**overrides):
    values = {
        "environment": "production",
        "database_url": "postgresql+asyncpg://interview:prod-db-pass@db.example.com:5432/interview_agent",
        "jwt_secret": "prod-jwt-test-value",
        "auth_dev_code_enabled": False,
        "auth_dev_code": "654321",
        "deepseek_api_key": "prod-deepseek-test-key",
        "llm_pricing_version": "llm-pricing-v1-test",
        "admin_phones": "",
        "rate_limit_backend": "redis",
        "redis_url": "redis://redis.example.com:6379/0",
        "async_job_backend": "redis",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


class SettingsGovernanceTest(unittest.TestCase):
    def test_development_defaults_are_allowed(self) -> None:
        settings = Settings(_env_file=None)

        settings.validate_production_config()

        self.assertFalse(settings.is_production)
        self.assertTrue(settings.auth_dev_code_enabled)

    def test_production_rejects_default_jwt_secret(self) -> None:
        settings = _production_settings(jwt_secret=DEFAULT_JWT_SECRET)

        with self.assertRaises(ConfigValidationError) as ctx:
            settings.validate_production_config()

        self.assertIn("JWT_SECRET", str(ctx.exception))
        self.assertNotIn(DEFAULT_JWT_SECRET, str(ctx.exception))

    def test_production_rejects_default_dev_code_even_when_disabled(self) -> None:
        settings = _production_settings(auth_dev_code=DEFAULT_DEV_CODE)

        with self.assertRaises(ConfigValidationError) as ctx:
            settings.validate_production_config()

        self.assertIn("AUTH_DEV_CODE", str(ctx.exception))
        self.assertNotIn(DEFAULT_DEV_CODE, str(ctx.exception))

    def test_production_rejects_enabled_dev_code(self) -> None:
        settings = _production_settings(auth_dev_code_enabled=True)

        with self.assertRaises(ConfigValidationError) as ctx:
            settings.validate_production_config()

        self.assertIn("AUTH_DEV_CODE_ENABLED", str(ctx.exception))

    def test_production_requires_llm_api_key_for_real_provider(self) -> None:
        settings = _production_settings(deepseek_api_key="", llm_provider="deepseek")

        with self.assertRaises(ConfigValidationError) as ctx:
            settings.validate_production_config()

        self.assertIn("DEEPSEEK_API_KEY", str(ctx.exception))

    def test_production_allows_mock_llm_without_api_key(self) -> None:
        settings = _production_settings(deepseek_api_key="", llm_provider="mock")

        settings.validate_production_config()

    def test_invalid_access_token_expiry_fails(self) -> None:
        with self.assertRaises(ValidationError):
            Settings(_env_file=None, access_token_expire_minutes=0)

    def test_invalid_rate_limit_value_fails(self) -> None:
        with self.assertRaises(ValidationError):
            Settings(_env_file=None, login_rate_limit_per_minute=0)

    def test_invalid_llm_gateway_retry_value_fails(self) -> None:
        with self.assertRaises(ValidationError):
            Settings(_env_file=None, llm_max_retries=0)

    def test_invalid_async_job_config_fails(self) -> None:
        with self.assertRaises(ValidationError):
            Settings(_env_file=None, async_job_backend="invalid")
        with self.assertRaises(ValidationError):
            Settings(_env_file=None, async_job_max_attempts=0)
        with self.assertRaises(ValidationError):
            Settings(_env_file=None, async_job_worker_poll_seconds=0)

    def test_production_requires_rate_limit_enabled(self) -> None:
        settings = _production_settings(rate_limit_enabled=False)

        with self.assertRaises(ConfigValidationError) as ctx:
            settings.validate_production_config()

        self.assertIn("RATE_LIMIT_ENABLED", str(ctx.exception))

    def test_production_rejects_memory_rate_limit_backend(self) -> None:
        settings = _production_settings(rate_limit_backend="memory")

        with self.assertRaises(ConfigValidationError) as ctx:
            settings.validate_production_config()

        self.assertIn("RATE_LIMIT_BACKEND", str(ctx.exception))

    def test_production_requires_redis_url_for_redis_rate_limit_backend(self) -> None:
        settings = _production_settings(redis_url="")

        with self.assertRaises(ConfigValidationError) as ctx:
            settings.validate_production_config()

        self.assertIn("REDIS_URL", str(ctx.exception))

    def test_production_rejects_memory_async_job_backend(self) -> None:
        settings = _production_settings(async_job_backend="memory")

        with self.assertRaises(ConfigValidationError) as ctx:
            settings.validate_production_config()

        self.assertIn("ASYNC_JOB_BACKEND", str(ctx.exception))

    def test_production_requires_redis_url_for_async_jobs(self) -> None:
        settings = _production_settings(rate_limit_enabled=False, async_job_backend="redis", redis_url="")

        with self.assertRaises(ConfigValidationError) as ctx:
            settings.validate_production_config()

        self.assertIn("REDIS_URL", str(ctx.exception))

    def test_missing_pricing_version_fails(self) -> None:
        settings = _production_settings(llm_pricing_version="")

        with self.assertRaises(ConfigValidationError) as ctx:
            settings.validate_production_config()

        self.assertIn("LLM_PRICING_VERSION", str(ctx.exception))

    def test_missing_admin_phones_is_not_fatal(self) -> None:
        settings = _production_settings(admin_phones="")

        settings.validate_production_config()

    def test_sanitized_config_summary_does_not_leak_sensitive_values(self) -> None:
        settings = _production_settings(
            database_url="postgresql+asyncpg://interview:db-password-for-test@db.example.com:5432/interview_agent",
            redis_url="redis://:redis-password-for-test@redis.example.com:6379/0",
            jwt_secret="jwt-value-for-test",
            auth_dev_code="112233",
            deepseek_api_key="deepseek-key-for-test",
            sms_provider_key="sms-key-for-test",
            whisper_api_key="whisper-key-for-test",
            admin_phones="13800000000,13900001111",
        )

        summary = settings.sanitized_config_summary()
        text = json.dumps(summary, sort_keys=True)

        self.assertNotIn("db-password-for-test", text)
        self.assertNotIn("redis-password-for-test", text)
        self.assertNotIn("jwt-value-for-test", text)
        self.assertNotIn("112233", text)
        self.assertNotIn("deepseek-key-for-test", text)
        self.assertNotIn("sms-key-for-test", text)
        self.assertNotIn("whisper-key-for-test", text)
        self.assertNotIn("13800000000", text)
        self.assertIn("138****0000", text)
        self.assertTrue(summary["auth"]["jwt_secret_configured"])
        self.assertTrue(summary["llm"]["deepseek_api_key_configured"])
        self.assertTrue(summary["llm"]["gateway_enabled"])
        self.assertEqual(summary["llm"]["fallback_provider"], "mock")
        self.assertEqual(summary["database"]["database_url"], "postgresql+asyncpg://interview:****@db.example.com:5432/interview_agent")
        self.assertTrue(summary["rate_limit"]["enabled"])
        self.assertGreater(summary["rate_limit"]["llm_daily_token_quota"], 0)
        self.assertTrue(summary["async_jobs"]["enabled"])
        self.assertEqual(summary["async_jobs"]["backend"], "redis")

    def test_production_rejects_real_gateway_route_without_api_key(self) -> None:
        settings = _production_settings(
            deepseek_api_key="",
            llm_provider="mock",
            llm_default_provider="mock",
            llm_route_interview_scoring="deepseek/deepseek-chat",
        )

        with self.assertRaises(ConfigValidationError) as ctx:
            settings.validate_production_config()

        self.assertIn("DEEPSEEK_API_KEY", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
