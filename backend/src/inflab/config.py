"""Application configuration models."""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFLAB_DATABASE_", extra="ignore")

    url: str = "postgresql+psycopg://inflab:inflab@127.0.0.1:5432/inflab"
    pool_size: int = 5
    pool_timeout_seconds: int = 30
    create_schema_on_startup: bool = False


class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFLAB_REDIS_", extra="ignore")

    url: str = "redis://127.0.0.1:6379/0"
    queue_name: str = "default"
    job_mode: Literal["sync", "rq"] = "sync"


class ObjectStorageSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFLAB_S3_", extra="ignore")

    endpoint_url: str = "http://127.0.0.1:9000"
    bucket_name: str = "inflab-artifacts"
    access_key_id: str = "inflabminio"
    secret_access_key: SecretStr = SecretStr("inflabminio")
    region_name: str = "us-east-1"


class SSHSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFLAB_SSH_", extra="ignore")

    default_timeout_seconds: int = 30
    known_hosts_policy: Literal["permissive", "strict"] = "permissive"
    platform_user: str = "inflab"


class LLMProviderSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="INFLAB_LLM_", extra="ignore")

    provider: Literal["disabled", "openai_compatible", "anthropic"] = "disabled"
    base_url: str | None = None
    api_key: SecretStr | None = None
    model: str | None = None


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore", populate_by_name=True)

    app_name: str = Field(default="InferenceLab API", validation_alias="INFLAB_APP_NAME")
    environment: str = Field(default="local", validation_alias="INFLAB_ENVIRONMENT")
    log_level: str = Field(default="INFO", validation_alias="INFLAB_LOG_LEVEL")
    secret_key: SecretStr = Field(
        default=SecretStr("inference-lab-dev-key"),
        validation_alias="INFLAB_SECRET_KEY",
    )
    seed_demo_data: bool = Field(default=False, validation_alias="INFLAB_SEED_DEMO_DATA")
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    object_storage: ObjectStorageSettings = Field(default_factory=ObjectStorageSettings)
    ssh: SSHSettings = Field(default_factory=SSHSettings)
    llm_provider: LLMProviderSettings = Field(default_factory=LLMProviderSettings)


@lru_cache
def get_settings() -> AppSettings:
    return AppSettings()
