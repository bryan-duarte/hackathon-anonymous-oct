from frontier.contracts.prompts import PromptId


class DuplicatePromptIdError(ValueError):
    def __init__(self, prompt_id: PromptId) -> None:
        super().__init__(f"duplicate prompt id: {prompt_id}")


class MissingPromptsError(ValueError):
    def __init__(self, missing_ids: set[PromptId]) -> None:
        super().__init__(f"prompts missing for ids: {', '.join(sorted(missing_ids))}")
