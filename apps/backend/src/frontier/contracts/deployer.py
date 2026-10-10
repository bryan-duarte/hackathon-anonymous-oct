from pydantic import Field

from frontier.contracts._base import StrictModel


class DeployRequest(StrictModel):
    job_id: str
    sandbox_id: str
    env_secret_refs: dict[str, str] = Field(
        default_factory=dict,
        description="Env var name -> secret handle; resolved server-side, never seen by the LLM.",
    )


class Deployment(StrictModel):
    deployment_id: str
    url: str
    status: str
