"""Application settings, loaded from environment / .env.

Connection settings keep their conventional env-var names (POSTGRES_*, etc.);
Autograde-specific knobs use the AUTOGRADE_ prefix. Everything is read once and
cached.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
        populate_by_name=True,
    )

    # Core
    env: str = Field(default="dev", alias="AUTOGRADE_ENV")
    log_level: str = Field(default="INFO", alias="AUTOGRADE_LOG_LEVEL")

    # Postgres
    postgres_host: str = Field(default="localhost", alias="POSTGRES_HOST")
    postgres_port: int = Field(default=5432, alias="POSTGRES_PORT")
    postgres_db: str = Field(default="autograde", alias="POSTGRES_DB")
    postgres_user: str = Field(default="autograde", alias="POSTGRES_USER")
    postgres_password: str = Field(default="change_me_locally", alias="POSTGRES_PASSWORD")
    student_hash_secret: str = Field(
        default="change_me_locally_32_bytes______", alias="STUDENT_HASH_SECRET"
    )

    # Messaging / cache / storage
    kafka_brokers: str = Field(default="localhost:9092", alias="KAFKA_BROKERS")
    redis_url: str = Field(default="redis://localhost:6379/0", alias="REDIS_URL")
    minio_endpoint: str = Field(default="localhost:9000", alias="MINIO_ENDPOINT")
    minio_access_key: str = Field(default="autograde", alias="MINIO_ACCESS_KEY")
    minio_secret_key: str = Field(default="change_me_locally", alias="MINIO_SECRET_KEY")
    minio_bucket_prefix: str = Field(default="autograde-", alias="MINIO_BUCKET_PREFIX")
    qdrant_url: str = Field(default="http://localhost:6333", alias="QDRANT_URL")
    temporal_address: str = Field(default="localhost:7233", alias="TEMPORAL_ADDRESS")

    # Observability
    otel_endpoint: str | None = Field(default=None, alias="OTEL_EXPORTER_OTLP_ENDPOINT")

    # LLM
    llm_backend: str = Field(default="local", alias="LLM_BACKEND")
    ollama_url: str = Field(default="http://localhost:11434", alias="OLLAMA_URL")
    # Phase 3 resolved decision: 3b defaults for CPU inference; the plan's 32B
    # targets are the scale-up path once hardware allows.
    local_model_theory: str = Field(default="qwen2.5:3b", alias="LOCAL_MODEL_THEORY")
    local_model_code: str = Field(default="qwen2.5:3b", alias="LOCAL_MODEL_CODE")
    # Small model for the QuestionMapper classification call (Phase 1).
    local_model_map: str = Field(default="qwen2.5:3b", alias="LOCAL_MODEL_MAP")

    # Sandbox (Phase 3): command prefix reaching the gVisor-enabled docker
    # engine. On this Windows box that is the native engine inside WSL2 Ubuntu;
    # on Linux it is just "docker".
    sandbox_docker_cmd: str = Field(
        default="wsl -d Ubuntu -u root -- docker -H unix:///run/docker-native.sock",
        alias="SANDBOX_DOCKER_CMD",
    )
    sandbox_runtime: str = Field(default="runsc", alias="SANDBOX_RUNTIME")
    sandbox_image: str = Field(default="python:3.11-slim", alias="SANDBOX_IMAGE")
    sandbox_pool_size: int = Field(default=2, alias="SANDBOX_POOL_SIZE")
    sandbox_timeout_s: int = Field(default=10, alias="SANDBOX_TIMEOUT_S")
    # Directory shared with the sandbox engine. Windows writes via the
    # \\wsl.localhost UNC path; containers bind-mount the Linux-side path.
    sandbox_exchange_win: str = Field(
        default=r"\\wsl.localhost\Ubuntu\tmp\autograde-sandbox",
        alias="SANDBOX_EXCHANGE_WIN",
    )
    sandbox_exchange_linux: str = Field(
        default="/tmp/autograde-sandbox", alias="SANDBOX_EXCHANGE_LINUX"
    )
    anthropic_api_key: str | None = Field(default=None, alias="ANTHROPIC_API_KEY")
    openai_api_key: str | None = Field(default=None, alias="OPENAI_API_KEY")

    @property
    def postgres_dsn(self) -> str:
        return (
            f"postgresql+psycopg://{self.postgres_user}:{self.postgres_password}"
            f"@{self.postgres_host}:{self.postgres_port}/{self.postgres_db}"
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
