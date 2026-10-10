from frontier.contracts.llm import AgentRole


class MissingRoleModelsError(ValueError):
    def __init__(self, missing_roles: set[AgentRole]) -> None:
        super().__init__(f"no model configured for roles: {', '.join(sorted(missing_roles))}")
