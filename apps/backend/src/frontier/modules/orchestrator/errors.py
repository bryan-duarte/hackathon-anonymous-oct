from pydantic import BaseModel


class MissingStructuredResponseError(RuntimeError):
    def __init__(self, expected_schema: type[BaseModel]) -> None:
        super().__init__(f"deep agent returned no structured {expected_schema.__name__}")


class MigrationTimedOutError(TimeoutError):
    def __init__(self, timeout_s: int) -> None:
        super().__init__(f"migration exceeded {timeout_s}s")


class ArtifactExportFailedError(RuntimeError):
    def __init__(self, job_id: str) -> None:
        super().__init__(f"migration {job_id} finished but its artifacts could not be exported")


class MigrationTimeoutTooShortError(ValueError):
    def __init__(self, sandbox_timeout_s: int, export_margin_s: int) -> None:
        super().__init__(
            f"migration sandbox timeout {sandbox_timeout_s}s must exceed the "
            f"{export_margin_s}s reserved for exporting artifacts"
        )


class SkillUploadError(RuntimeError):
    def __init__(self, failed_paths: list[str]) -> None:
        super().__init__(f"could not upload coder skill files: {', '.join(failed_paths)}")
