import pytest

from frontier.modules.sandbox import InvalidSandboxEnvError
from frontier.modules.sandbox.docker_driver import _env_file_content


def test_env_file_lists_one_entry_per_line() -> None:
    env_file_content = _env_file_content({"SERVICE_KEY": "s3cret=value", "MODE": ""})

    assert env_file_content == "SERVICE_KEY=s3cret=value\nMODE=\n"


@pytest.mark.parametrize(
    "unsafe_env",
    [
        {"DOCKER HOST": "x"},
        {"A=B": "x"},
        {"1NAME": "x"},
        {"SERVICE_KEY": "line-one\nINJECTED=1"},
    ],
)
def test_env_file_rejects_unsafe_entries(unsafe_env: dict[str, str]) -> None:
    with pytest.raises(InvalidSandboxEnvError):
        _env_file_content(unsafe_env)
