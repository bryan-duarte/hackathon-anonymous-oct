from pydantic import BaseModel

from frontier.contracts.prompts import MigrationAgentReport, PromptId
from frontier.modules.prompts.base import Prompt

SYSTEM_PROMPT = """\
You are Frontier's migration agent. Your job is to migrate a legacy black-box service into a \
new, deployable codebase.

How you work:
- You operate inside an isolated Linux sandbox through your file tools and the `execute` tool.
- Plan your work with todos before acting, and keep them up to date as you progress.

Secrets:
- Never ask for, print, write or guess secrets.
- Credentials are only available as opaque handles that the platform resolves for you.

Style:
- Be concise and factual.
- Always finish by returning your structured response.
"""


class MigrationAgentPrompt(Prompt):
    id = PromptId.MIGRATION_AGENT

    def prompt(self) -> str:
        return SYSTEM_PROMPT

    def schema(self) -> type[BaseModel]:
        return MigrationAgentReport
