from frontier.contracts._base import StrictModel


class DelegateTaskRequest(StrictModel):
    job_id: str
    agent_name: str
    instructions: str


class DelegateTaskResult(StrictModel):
    output: str
