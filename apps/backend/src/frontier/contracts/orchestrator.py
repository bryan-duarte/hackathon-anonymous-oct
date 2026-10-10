from frontier.contracts._base import StrictModel


class RunMigrationRequest(StrictModel):
    job_id: str
    base_url: str
    context: str
    service_key_ref: str
    team_token_ref: str


class RunMigrationResult(StrictModel):
    deployed_url: str
