from pathlib import Path
from typing import Literal, Self

from pydantic import Field, SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from frontier.core.logging_config import LogFormat

OPENROUTER_API_URL = "https://openrouter.ai/api"

SandboxProvider = Literal["vercel", "docker"]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FRONTIER_", env_file=".env", extra="ignore")

    platform_api_key: SecretStr
    secrets_master_key: SecretStr
    database_path: Path = Path("data/frontier.db")
    checkpoint_database_path: Path = Path("data/checkpoints.db")
    max_concurrent_jobs: int = Field(default=1, ge=1)
    log_format: LogFormat = "console"

    openrouter_api_key: SecretStr = Field(validation_alias="OPENROUTER_API_KEY", min_length=1)
    vercel_token: SecretStr | None = Field(
        default=None, validation_alias="VERCEL_TOKEN", min_length=1
    )
    vercel_team_id: str | None = Field(
        default=None, validation_alias="VERCEL_TEAM_ID", min_length=1
    )
    vercel_project_id: str | None = Field(
        default=None, validation_alias="VERCEL_PROJECT_ID", min_length=1
    )

    llm_base_url: str = OPENROUTER_API_URL
    llm_model: str = "anthropic/claude-haiku-5.5"
    llm_max_tokens: int = Field(default=8192, ge=1)
    llm_timeout_s: float = Field(default=120, gt=0)
    llm_max_retries: int = Field(default=2, ge=0)

    guardrail_url: str = f"{OPENROUTER_API_URL}/alpha/decisions"
    guardrail_model: str = "typesafe/jev-1.13"
    guardrail_timeout_s: float = Field(default=15, gt=0)
    guardrail_block_threshold: float = Field(default=0.5, ge=0, le=1)
    guardrail_chunk_chars: int = Field(default=60_000, ge=10_000)

    sandbox_provider: SandboxProvider = "vercel"
    sandbox_runtime: str = "python3.13"
    sandbox_docker_image: str = "python:3.13"
    sandbox_timeout_s: int = Field(default=600, gt=0)
    sandbox_command_timeout_s: int = Field(default=300, gt=0)

    orchestrator_model: str | None = None
    analyst_model: str | None = None
    scientist_model: str | None = None
    coder_model: str | None = None
    migration_sandbox_timeout_s: int = Field(default=2700, gt=0)
    migration_max_phase_attempts: int = Field(default=3, ge=1)
    artifacts_dir: Path = Path("data/artifacts")
    probe_timeout_s: float = Field(default=15, gt=0)

    @model_validator(mode="after")
    def _require_vercel_credentials_for_vercel_sandbox(self) -> Self:
        missing_credentials = [
            env_name
            for env_name, credential in (
                ("VERCEL_TOKEN", self.vercel_token),
                ("VERCEL_TEAM_ID", self.vercel_team_id),
                ("VERCEL_PROJECT_ID", self.vercel_project_id),
            )
            if credential is None
        ]
        vercel_sandbox_misconfigured = self.sandbox_provider == "vercel" and missing_credentials
        if vercel_sandbox_misconfigured:
            raise ValueError(
                f"FRONTIER_SANDBOX_PROVIDER=vercel requires {', '.join(missing_credentials)}"
            )
        return self
