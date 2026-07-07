from __future__ import annotations

from functools import lru_cache

from pydantic import AliasChoices, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Interview Agent"
    api_prefix: str = "/api"
    environment: str = Field(default="development", validation_alias=AliasChoices("APP_ENV", "ENVIRONMENT"))

    database_url: str = Field(
        default="postgresql+asyncpg://interview:local-dev-only@localhost:5432/interview_agent",
        validation_alias="DATABASE_URL",
    )
    redis_url: str = Field(default="redis://localhost:6379/0", validation_alias="REDIS_URL")

    deepseek_api_key: str = Field(default="", validation_alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(default="https://api.deepseek.com", validation_alias="DEEPSEEK_BASE_URL")
    deepseek_model: str = Field(default="deepseek-chat", validation_alias="DEEPSEEK_MODEL")
    llm_timeout_seconds: float = Field(default=45.0, validation_alias="LLM_TIMEOUT_SECONDS")

    embedding_model: str = Field(default="BAAI/bge-large-zh-v1.5", validation_alias="EMBEDDING_MODEL")
    whisper_api_key: str = Field(default="", validation_alias="WHISPER_API_KEY")
    whisper_base_url: str = Field(default="https://api.siliconflow.cn/v1", validation_alias="WHISPER_BASE_URL")
    whisper_model: str = Field(default="FunAudioLLM/SenseVoiceSmall", validation_alias="WHISPER_MODEL")
    sms_provider_key: str = Field(default="", validation_alias="SMS_PROVIDER_KEY")
    auth_dev_code_enabled: bool = Field(default=True, validation_alias="AUTH_DEV_CODE_ENABLED")
    auth_dev_code: str = Field(default="000000", validation_alias="AUTH_DEV_CODE")
    access_token_expire_minutes: int = Field(default=24 * 60, validation_alias="ACCESS_TOKEN_EXPIRE_MINUTES")
    jwt_secret: str = Field(
        default="local-dev-only-change-me",
        validation_alias=AliasChoices("JWT_SECRET_KEY", "TOKEN_SECRET", "JWT_SECRET"),
    )
    admin_phones: str = Field(default="", validation_alias="ADMIN_PHONES")
    cors_origins: str = Field(default="http://localhost:3000", validation_alias="CORS_ORIGINS")

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def admin_phone_set(self) -> set[str]:
        return {phone.strip() for phone in self.admin_phones.split(",") if phone.strip()}

    @property
    def is_production(self) -> bool:
        return self.environment.strip().lower() in {"prod", "production"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
