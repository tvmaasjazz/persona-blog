OUTLINE_USER_TEMPLATE = (
    "Write an outline for a blog post based on the following brief:\n\n{prompt_text}"
)

DRAFT_USER_TEMPLATE = (
    "Write a full blog post draft based on the following outline:\n\n{outline_text}\n\n"
    "Original brief:\n\n{prompt_text}"
)

HUMANIZE_USER_TEMPLATE = (
    "Rewrite the following blog post draft so it reads like a human wrote it, removing "
    "anything that reads as AI-generated:\n\n{draft_text}"
)

REWRITE_OUTLINE_USER_TEMPLATE = (
    "Here is the current outline:\n\n{previous_output}\n\n"
    "A reviewer left the following feedback. Rewrite the outline to address it:\n\n{feedback_text}"
)

REWRITE_DRAFT_USER_TEMPLATE = (
    "Here is the current draft:\n\n{previous_output}\n\n"
    "A reviewer left the following feedback. Rewrite the draft to address it:\n\n{feedback_text}"
)

REWRITE_HUMANIZE_USER_TEMPLATE = (
    "Here is the current humanized version:\n\n{previous_output}\n\n"
    "A reviewer left the following feedback. Rewrite it to address the feedback:\n\n{feedback_text}"
)

PERSONA_INFO_SECTION_TEMPLATE = "\n\nPersona:\n\n{persona_info}"

ADDITIONAL_CONTEXT_SECTION_TEMPLATE = "\n\nAdditional context:\n\n{additional_context}"


class BlogPostPrompt:
    """Prompt builders for every blog post step and every rewrite. Each takes
    persona_info and additional_context when present, appended as extra sections."""

    @staticmethod
    def build_outline_prompt(
        prompt_text: str, persona_info: str | None, additional_context: str | None
    ) -> str:
        base_prompt = OUTLINE_USER_TEMPLATE.format(prompt_text=prompt_text)
        return base_prompt + BlogPostPrompt._build_context_suffix(persona_info, additional_context)

    @staticmethod
    def build_draft_prompt(
        prompt_text: str,
        outline_text: str,
        persona_info: str | None,
        additional_context: str | None,
    ) -> str:
        base_prompt = DRAFT_USER_TEMPLATE.format(prompt_text=prompt_text, outline_text=outline_text)
        return base_prompt + BlogPostPrompt._build_context_suffix(persona_info, additional_context)

    @staticmethod
    def build_humanize_prompt(
        draft_text: str, persona_info: str | None, additional_context: str | None
    ) -> str:
        base_prompt = HUMANIZE_USER_TEMPLATE.format(draft_text=draft_text)
        return base_prompt + BlogPostPrompt._build_context_suffix(persona_info, additional_context)

    @staticmethod
    def build_rewrite_outline_prompt(
        previous_output: str,
        feedback_text: str,
        persona_info: str | None,
        additional_context: str | None,
    ) -> str:
        base_prompt = REWRITE_OUTLINE_USER_TEMPLATE.format(
            previous_output=previous_output, feedback_text=feedback_text
        )
        return base_prompt + BlogPostPrompt._build_context_suffix(persona_info, additional_context)

    @staticmethod
    def build_rewrite_draft_prompt(
        previous_output: str,
        feedback_text: str,
        persona_info: str | None,
        additional_context: str | None,
    ) -> str:
        base_prompt = REWRITE_DRAFT_USER_TEMPLATE.format(
            previous_output=previous_output, feedback_text=feedback_text
        )
        return base_prompt + BlogPostPrompt._build_context_suffix(persona_info, additional_context)

    @staticmethod
    def build_rewrite_humanize_prompt(
        previous_output: str,
        feedback_text: str,
        persona_info: str | None,
        additional_context: str | None,
    ) -> str:
        base_prompt = REWRITE_HUMANIZE_USER_TEMPLATE.format(
            previous_output=previous_output, feedback_text=feedback_text
        )
        return base_prompt + BlogPostPrompt._build_context_suffix(persona_info, additional_context)

    @staticmethod
    def _build_context_suffix(persona_info: str | None, additional_context: str | None) -> str:
        context_suffix = ""
        if persona_info:
            context_suffix += PERSONA_INFO_SECTION_TEMPLATE.format(persona_info=persona_info)
        if additional_context:
            context_suffix += ADDITIONAL_CONTEXT_SECTION_TEMPLATE.format(
                additional_context=additional_context
            )
        return context_suffix
