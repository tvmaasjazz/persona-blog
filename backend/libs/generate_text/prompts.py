from libs.generate_text.types import TextType

SYSTEM_TEMPLATE = "You are a skilled writer producing text for a human editor to review."

USER_TEMPLATE = "Write a {text_type} based on the following brief:\n\n{prompt_text}"

REWRITE_USER_TEMPLATE = (
    "Here is the current draft:\n\n{draft_text}\n\n"
    "A reviewer left the following feedback. Rewrite the draft to address it:\n\n{feedback_text}"
)


class GenerateTextPrompt:
    @staticmethod
    def build_system_prompt() -> str:
        return SYSTEM_TEMPLATE

    @staticmethod
    def build_user_prompt(prompt_text: str, text_type: TextType) -> str:
        return USER_TEMPLATE.format(
            text_type=text_type.value.lower().replace("_", " "), prompt_text=prompt_text
        )

    @staticmethod
    def build_rewrite_user_prompt(draft_text: str, feedback_text: str) -> str:
        return REWRITE_USER_TEMPLATE.format(draft_text=draft_text, feedback_text=feedback_text)
