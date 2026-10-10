class UnknownSandboxError(LookupError):
    def __init__(self, sandbox_id: str) -> None:
        super().__init__(f"no live job sandbox with id {sandbox_id}")


class WorkspaceListingError(RuntimeError):
    def __init__(self, sandbox_id: str, stderr: str) -> None:
        super().__init__(f"could not list workspace files in sandbox {sandbox_id}: {stderr}")
