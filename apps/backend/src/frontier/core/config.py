from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="FRONTIER_", env_file=".env", extra="ignore")

    platform_api_key: SecretStr
    secrets_master_key: SecretStr
    database_path: Path = Path("data/frontier.db")
    max_concurrent_jobs: int = Field(default=1, ge=1)
