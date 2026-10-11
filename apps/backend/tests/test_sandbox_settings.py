import pytest
from pydantic import ValidationError

from frontier.core.config import Settings

BASE_ENV = {
    "FRONTIER_PLATFORM_API_KEY": "platform-key",
    "FRONTIER_SECRETS_MASTER_KEY": "master-key",
    "OPENROUTER_API_KEY": "openrouter-key",
}
VERCEL_ENV = {
    "VERCEL_TOKEN": "vercel-token",
    "VERCEL_TEAM_ID": "team-id",
    "VERCEL_PROJECT_ID": "project-id",
}


@pytest.fixture(autouse=True)
def _isolated_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for env_name in [*VERCEL_ENV, "FRONTIER_SANDBOX_PROVIDER"]:
        monkeypatch.delenv(env_name, raising=False)
    for env_name, env_value in BASE_ENV.items():
        monkeypatch.setenv(env_name, env_value)


def test_docker_provider_does_not_need_vercel_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRONTIER_SANDBOX_PROVIDER", "docker")

    settings = Settings(_env_file=None)

    assert settings.sandbox_provider == "docker"
    assert settings.vercel_token is None


def test_vercel_is_the_default_provider_and_requires_its_credentials() -> None:
    with pytest.raises(ValidationError, match="VERCEL_TOKEN, VERCEL_TEAM_ID, VERCEL_PROJECT_ID"):
        Settings(_env_file=None)


def test_vercel_provider_loads_with_its_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    for env_name, env_value in VERCEL_ENV.items():
        monkeypatch.setenv(env_name, env_value)

    settings = Settings(_env_file=None)

    assert settings.sandbox_provider == "vercel"
    assert settings.vercel_team_id == "team-id"


def test_unknown_provider_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("FRONTIER_SANDBOX_PROVIDER", "kubernetes")

    with pytest.raises(ValidationError, match="sandbox_provider"):
        Settings(_env_file=None)
