class UnknownSandboxError(LookupError):
    def __init__(self, sandbox_id: str) -> None:
        super().__init__(f"no live job sandbox with id {sandbox_id}")


class InvalidSandboxEnvError(ValueError):
    def __init__(self, env_name: str) -> None:
        super().__init__(f"env var {env_name!r} has an invalid name or a multi-line value")


class SandboxStartError(RuntimeError):
    def __init__(self, stderr: str) -> None:
        super().__init__(f"could not start sandbox: {stderr}")


class WorkspaceListingError(RuntimeError):
    def __init__(self, sandbox_id: str, stderr: str) -> None:
        super().__init__(f"could not list workspace files in sandbox {sandbox_id}: {stderr}")
