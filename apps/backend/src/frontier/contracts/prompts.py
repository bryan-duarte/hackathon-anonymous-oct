from enum import StrEnum

from pydantic import Field

from frontier.contracts._base import StrictModel


class PromptId(StrEnum):
    MIGRATION_AGENT = "migration_agent"
    GREETING = "greeting"


class Greeting(StrictModel):
    greeting: str = Field(description="A short, friendly greeting from the agent.")


class MigrationAgentReport(StrictModel):
    summary: str = Field(description="What the agent did and found.")
