from __future__ import annotations

from functools import lru_cache
from typing import Any
from urllib.parse import urlsplit, urlunsplit

from pydantic import AliasChoices, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


DEFAULT_DEV_CODE = "000000"
DEFAULT_JWT_SECRET = "local-dev-only-change-me"
DEFAULT_LLM_PRICING_VERSION = "llm-pricing-v1-2026-07"


class ConfigValidationError(RuntimeError):
    pass


class Settings(BaseSettings):
    # App config
    app_name: str = Field(default="Interview Agent", validation_alias=AliasChoices("SERVICE_NAME", "APP_NAME"))
    api_prefix: str = Field(default="/api", validation_alias="API_PREFIX")
    environment: str = Field(default="development", validation_alias=AliasChoices("APP_ENV", "ENVIRONMENT"))

    # Database / infrastructure config
    database_url: str = Field(
        default="postgresql+asyncpg://interview:local-dev-only@localhost:5432/interview_agent",
        validation_alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")

    # LLM config
    llm_provider: str = Field(default="deepseek", validation_alias="LLM_PROVIDER")
    deepseek_api_key: str = Field(default="", validation_alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(default="https://api.deepseek.com", validation_alias="DEEPSEEK_BASE_URL")
    deepseek_model: str = Field(default="deepseek-chat", validation_alias="DEEPSEEK_MODEL")
    llm_timeout_seconds: float = Field(default=45.0, validation_alias="LLM_TIMEOUT_SECONDS")
    llm_pricing_version: str = Field(default=DEFAULT_LLM_PRICING_VERSION, validation_alias="LLM_PRICING_VERSION")

    # Model / audio config
    embedding_model: str = Field(default="BAAI/bge-large-zh-v1.5", validation_alias="EMBEDDING_MODEL")
    whisper_api_key: str = Field(default="", validation_alias="WHISPER_API_KEY")
    whisper_base_url: str = Field(default="https://api.siliconflow.cn/v1", validation_alias="WHISPER_BASE_URL")
    whisper_model: str = Field(default="FunAudioLLM/SenseVoiceSmall", validation_alias="WHISPER_MODEL")

    # Auth config
    sms_provider_key: str = Field(default="", validation_alias="SMS_PROVIDER_KEY")
    auth_dev_code_enabled: bool = Field(default=True, validation_alias="AUTH_DEV_CODE_ENABLED")
    auth_dev_code: str = Field(default=DEFAULT_DEV_CODE, validation_alias="AUTH_DEV_CODE")
    access_token_expire_minutes: int = Field(default=24 * 60, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    jwt_secret: str = Field(
        default=DEFAULT_JWT_SECRET,
        validation_alias=AliasChoices("JWT_SECRET_KEY", "TOKEN_SECRET", "JWT_SECRET"),
    )

    # Admin config
    admin_phones: str = Field(default="", validation_alias="ADMIN_PHONES")

    # HTTP / frontend config
    cors_origins: str = Field(default="http://localhost:3000", validation_alias="CORS_ORIGINS")

    # Observability config
    log_level: str = Field(default="INFO", validation_alias="LOG_LEVEL")
    log_format: str = Field(default="json", validation_alias="LOG_FORMAT")
    request_id_header: str = Field(default="X-Request-ID", validation_alias="REQUEST_ID_HEADER")

    # Usage metering config
    llm_usage_metering_enabled: bool = Field(default=True, validation_alias="LLM_USAGE_METERING_ENABLED")

    # Rate limit / quota config
    rate_limit_enabled: bool = Field(default=True, validation_alias="RATE_LIMIT_ENABLED")
    login_rate_limit_per_minute: int = Field(default=600, validation_alias="LOGIN_RATE_LIMIT_PER_MINUTE")
    auth_phone_rate_limit_per_hour: int = Field(default=600, validation_alias="AUTH_PHONE_RATE_LIMIT_PER_HOUR")
    answer_submit_rate_limit_per_minute: int = Field(default=600, validation_alias="ANSWER_SUBMIT_RATE_LIMIT_PER_MINUTE")
    llm_daily_token_quota: int = Field(default=1_000_000, validation_alias="LLM_DAILY_TOKEN_QUOTA")
    llm_monthly_token_quota: int = Field(default=10_000_000, validation_alias="LLM_MONTHLY_TOKEN_QUOTA")
    llm_daily_call_quota: int = Field(default=1_000, validation_alias="LLM_DAILY_CALL_QUOTA")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore", populate_by_name=True)

    @field_validator("access_token_expire_minutes")
    @classmethod
    def _validate_access_token_expire_minutes(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("ACCESS_TOKEN_EXPIRE_MINUTES must be positive")
        return value

    @field_validator("llm_timeout_seconds")
    @classmethod
    def _validate_llm_timeout_seconds(cls, value: float) -> float:
        if value <= 0:
            raise ValueError("LLM_TIMEOUT_SECONDS must be positive")
        return value

    @field_validator(
        "login_rate_limit_per_minute",
        "auth_phone_rate_limit_per_hour",
        "answer_submit_rate_limit_per_minute",
        "llm_daily_token_quota",
        "llm_monthly_token_quota",
        "llm_daily_call_quota",
    )
    @classmethod
    def _validate_positive_limits(cls, value: int) -> int:
        if value <= 0:
            raise ValueError("Rate limit and quota values must be positive")
        return value

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def admin_phone_set(self) -> set[str]:
        return {phone.strip() for phone in self.admin_phones.split(",") if phone.strip()}

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() in {"prod", "production"}

    @property
    def normalized_llm_provider(self) -> str:
        return self.llm_provider.strip().lower() or "unknown"

    @property
    def uses_real_llm_provider(self) -> bool:
        return self.normalized_llm_provider not in {"", "mock", "local", "local-fallback", "none"}

    def validate_production_config(self) -> None:
        errors: list[str] = []
        if not self.database_url.strip():
            errors.append("DATABASE_URL is required")
        if self.access_token_expire_minutes <= 0:
            errors.append("ACCESS_TOKEN_EXPIRE_MINUTES must be positive")
        if not self.llm_pricing_version.strip():
            errors.append("LLM_PRICING_VERSION is required")

        if self.is_production:
            if not self.rate_limit_enabled:
                errors.append("RATE_LIMIT_ENABLED must be true in production")
            if self.jwt_secret == DEFAULT_JWT_SECRET:
                errors.append("JWT_SECRET_KEY/TOKEN_SECRET/JWT_SECRET must be configured for production")
            if self.auth_dev_code == DEFAULT_DEV_CODE:
                errors.append("AUTH_DEV_CODE must not use the default development code in production")
            if self.auth_dev_code_enabled:
                errors.append("AUTH_DEV_CODE_ENABLED must be false in production")
            if self.uses_real_llm_provider and not self.deepseek_api_key.strip():
                errors.append("DEEPSEEK_API_KEY is required when production LLM provider is enabled")

        if errors:
            raise ConfigValidationError("; ".join(errors))

    def sanitized_config_summary(self) -> dict[str, Any]:
        return {
            "app": {
                "service_name": self.app_name,
                "api_prefix": self.api_prefix,
                "environment": self.environment,
                "cors_origins": self.cors_origin_list,
            },
            "database": {
                "database_url": _mask_url(self.database_url),
                "redis_url": _mask_url(self.redis_url),
            },
            "auth": {
                "dev_code_enabled": self.auth_dev_code_enabled,
                "dev_code_configured": bool(self.auth_dev_code),
                "access_token_expire_minutes": self.access_token_expire_minutes,
                "jwt_secret_configured": bool(self.jwt_secret),
                "sms_provider_configured": bool(self.sms_provider_key),
            },
            "admin": {
                "admin_phones": [_mask_phone(phone) for phone in sorted(self.admin_phone_set)],
                "admin_phone_count": len(self.admin_phone_set),
            },
            "llm": {
                "provider": self.normalized_llm_provider,
                "deepseek_api_key_configured": bool(self.deepseek_api_key),
                "deepseek_base_url": self.deepseek_base_url,
                "deepseek_model": self.deepseek_model,
                "timeout_seconds": self.llm_timeout_seconds,
                "pricing_version": self.llm_pricing_version,
            },
            "observability": {
                "log_level": self.log_level,
                "log_format": self.log_format,
                "request_id_header": self.request_id_header,
            },
            "usage_metering": {
                "enabled": self.llm_usage_metering_enabled,
                "pricing_version": self.llm_pricing_version,
            },
            "rate_limit": {
                "enabled": self.rate_limit_enabled,
                "login_per_minute": self.login_rate_limit_per_minute,
                "auth_phone_per_hour": self.auth_phone_rate_limit_per_hour,
                "answer_submit_per_minute": self.answer_submit_rate_limit_per_minute,
                "llm_daily_token_quota": self.llm_daily_token_quota,
                "llm_monthly_token_quota": self.llm_monthly_token_quota,
                "llm_daily_call_quota": self.llm_daily_call_quota,
            },
        }


def _mask_phone(phone: str | None) -> str | None:
    if not phone:
        return None
    value = str(phone)
    if len(value) <= 4:
        return "****"
    return f"{value[:3]}****{value[-4:]}"


def _mask_url(value: str) -> str:
    if not value:
        return ""
    try:
        parsed = urlsplit(value)
    except ValueError:
        return "<invalid-url>"
    if not parsed.password:
        return value
    username = parsed.username or ""
    host = parsed.hostname or ""
    port = f":{parsed.port}" if parsed.port else ""
    netloc = f"{username}:****@{host}{port}" if username else f"****@{host}{port}"
    return urlunsplit((parsed.scheme, netloc, parsed.path, parsed.query, parsed.fragment))


@lru_cache
def get_settings() -> Settings:
    return Settings()
