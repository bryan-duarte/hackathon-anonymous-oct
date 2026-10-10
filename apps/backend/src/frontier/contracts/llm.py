from enum import StrEnum


class AgentRole(StrEnum):
    ORCHESTRATOR = "orchestrator"
    ANALYST = "analyst"
    SCIENTIST = "scientist"
    CODER = "coder"
