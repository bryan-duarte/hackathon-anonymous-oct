class HostOutsideScopeError(ValueError):
    def __init__(self, requested_url: str) -> None:
        super().__init__(f"{requested_url} is outside the legacy service base URL")


class NonPublicHostError(ValueError):
    def __init__(self, hostname: str) -> None:
        super().__init__(
            f"{hostname} resolves to a non-public address; only public APIs are probed"
        )
