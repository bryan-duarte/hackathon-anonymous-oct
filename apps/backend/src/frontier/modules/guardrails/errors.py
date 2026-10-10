class GuardrailUnavailableError(RuntimeError):
    def __init__(self, cause: str) -> None:
        super().__init__(f"guardrail decision model unavailable: {cause}")
