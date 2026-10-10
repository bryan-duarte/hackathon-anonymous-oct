from pydantic import BaseModel, ConfigDict


class StrictModel(BaseModel):
    """Internal module contract: no coercion, no unknown fields, immutable."""

    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class ApiModel(BaseModel):
    """HTTP edge contract: JSON needs coercion (enums, datetimes, URLs), so not strict."""

    model_config = ConfigDict(extra="forbid", frozen=True)
