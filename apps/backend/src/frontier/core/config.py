from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

from frontier.core.logging_config import LogFormat


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FRONTIER_", env_file=".env", extra="ignore")

    platform_api_key: SecretStr
    secrets_master_key: SecretStr
    database_path: Path = Path("data/frontier.db")
    max_concurrent_jobs: int = Field(default=1, ge=1)
    log_format: LogFormat = "console"

    openrouter_api_key: SecretStr = Field(validation_alias="OPENROUTER_API_KEY", min_length=1)
    vercel_token: SecretStr = Field(validation_alias="VERCEL_TOKEN", min_length=1)
    vercel_team_id: str = Field(validation_alias="VERCEL_TEAM_ID", min_length=1)
    vercel_project_id: str = Field(validation_alias="VERCEL_PROJECT_ID", min_length=1)

    llm_base_url: str = "https://openrouter.ai/api"
    llm_model: str = "anthropic/claude-haiku-5.5"
    llm_max_tokens: int = Field(default=8192, ge=1)
    llm_timeout_s: float = Field(default=120, gt=0)
    llm_max_retries: int = Field(default=2, ge=0)

    guardrail_url: str = "https://openrouter.ai/api/alpha/decisions"
    guardrail_model: str = "typesafe/jev-1.13"
    guardrail_timeout_s: float = Field(default=15, gt=0)
    guardrail_block_threshold: float = Field(default=0.5, ge=0, le=1)
    guardrail_chunk_chars: int = Field(default=60_000, ge=10_000)

    sandbox_runtime: str = "python3.13"
    sandbox_timeout_s: int = Field(default=600, gt=0)
    sandbox_command_timeout_s: int = Field(default=300, gt=0)
