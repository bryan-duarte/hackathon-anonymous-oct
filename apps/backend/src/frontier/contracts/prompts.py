from enum import StrEnum
from typing import Literal

from pydantic import Field

from frontier.contracts._base import StrictModel
from frontier.contracts.jobs import MigrationVerdictKind


class PromptId(StrEnum):
    MIGRATION_AGENT = "migration_agent"
    GREETING = "greeting"
    MIGRATION_ORCHESTRATOR = "migration_orchestrator"
    API_ANALYST = "api_analyst"
    API_SCIENTIST = "api_scientist"
    CODER = "coder"


class Greeting(StrictModel):
    greeting: str = Field(description="A short, friendly greeting from the agent.")


class MigrationAgentReport(StrictModel):
    summary: str = Field(description="What the agent did and found.")


class ApiSurfaceSummary(StrictModel):
    """Your final answer to the lead: produce it exactly once, as your last step, after
    writing the API surface report."""

    report_path: str = Field(description="Absolute sandbox path of the API surface report.")
    contract_source: str = Field(
        description="Where the endpoint list came from: a spec URL such as /openapi.json, "
        "the submitted context, or 'probing'."
    )
    http_base_reachable: bool = Field(description="The legacy base URL answered HTTP requests.")
    auth_scheme: str = Field(
        description="How the legacy service authenticates requests, or 'none' if it does not."
    )
    discovered_endpoints: list[str] = Field(
        description="Endpoints found, each as 'METHOD /path' (use '*' when the method is unknown)."
    )
    open_questions: list[str] = Field(description="Facts that could not be established.")


class BehaviorCatalogSummary(StrictModel):
    """Your final answer to the lead: produce it exactly once, as your last step, after
    writing the behavior report and behaviors.json."""

    report_path: str = Field(description="Absolute sandbox path of the behavior report.")
    catalogue_path: str = Field(description="Absolute sandbox path of behaviors.json.")
    endpoint_count: int = Field(description="Number of distinct endpoints characterized.")
    behavior_count: int = Field(description="Number of behaviors in behaviors.json.")
    error_case_count: int = Field(
        description="Number of behaviors whose expected status is 4xx or 5xx."
    )
    open_questions: list[str] = Field(description="Behaviors that could not be pinned down.")


class CodingSummary(StrictModel):
    """Your final answer to the lead: produce it exactly once, as your last step, after
    writing the coding report."""

    phase: Literal["characterization", "implementation"] = Field(
        description="Which coding task was performed."
    )
    report_path: str = Field(description="Absolute sandbox path of the coding report.")
    test_count: int = Field(description="Number of tests in the characterization suite.")
    legacy_suite_passed: bool = Field(description="Last run_characterization_suite(legacy) passed.")
    candidate_suite_passed: bool | None = Field(
        description="Last run_characterization_suite(candidate) passed; null if not run."
    )
    notes: str = Field(description="Decisions, suspected wrong tests and unresolved issues.")


class MigrationVerdict(StrictModel):
    """The migration verdict: produce it exactly once, as your last step, after your final
    hard checks."""

    verdict: MigrationVerdictKind = Field(
        strict=False, description="accepted only if every gate check passed."
    )
    summary: str = Field(description="What was migrated, evidence for the verdict, and any gaps.")
    uncovered_behavior_ids: list[str] = Field(
        description="Behavior IDs from behaviors.json without a characterization test. "
        "Empty to accept."
    )
    legacy_suite_passed: bool = Field(description="Last run_characterization_suite(legacy) passed.")
    candidate_suite_passed: bool = Field(
        description="Last run_characterization_suite(candidate) passed."
    )
    rejected_phases: list[str] = Field(description="Phases that hit the attempt cap, if any.")
