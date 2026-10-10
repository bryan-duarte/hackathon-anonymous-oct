from pydantic import BaseModel


class MissingStructuredResponseError(RuntimeError):
    def __init__(self, expected_schema: type[BaseModel]) -> None:
        super().__init__(f"deep agent returned no structured {expected_schema.__name__}")
