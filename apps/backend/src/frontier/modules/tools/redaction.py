from frontier.clients.secrets import SecretsClient
from frontier.contracts.secrets import RedactRequest
from frontier.contracts.tools import MigrationRunContext


async def redact_for_run(secrets: SecretsClient, text: str, context: MigrationRunContext) -> str:
    redacted = await secrets.redact(RedactRequest(text=text, refs=[context.service_key_ref]))
    return redacted.text
