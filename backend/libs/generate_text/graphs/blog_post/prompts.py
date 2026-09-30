from libs.generate_text.prompts import BaseGenerateTextPrompt
from libs.generate_text.results import BuildPromptResult
from libs.generate_text.states import GenerateTextState

OUTLINE_SYSTEM_PROMPT = (
    "Write an outline for a blog post: the sections it will cover, the key point each "
    "one makes, and the order they build in. Keep it a plan, not the prose itself."
)

DRAFT_SYSTEM_PROMPT = (
    "Write a complete blog post draft from the outline and brief provided. Write the "
    "full prose, ready for review — not another outline."
)

HUMANIZE_SYSTEM_PROMPT = (
    "Rewrite the given blog post draft so it reads like a person wrote it: vary "
    "sentence rhythm, cut filler and hedging, and remove anything that reads as "
    "AI-generated, while keeping the meaning and structure intact."
)

OUTLINE_USER_TEMPLATE = "Brief:\n\n{prompt_text}"

DRAFT_USER_TEMPLATE = "Outline:\n\n{outline_text}\n\nBrief:\n\n{prompt_text}"

HUMANIZE_USER_TEMPLATE = "Draft:\n\n{draft_text}"

REWRITE_OUTLINE_USER_TEMPLATE = (
    "Brief:\n\n{prompt_text}\n\n"
    "Current outline:\n\n{previous_output}\n\n"
    "A reviewer left the following feedback. Rewrite the outline to address it:\n\n{feedback_text}"
)

REWRITE_DRAFT_USER_TEMPLATE = (
    "Brief:\n\n{prompt_text}\n\n"
    "Current draft:\n\n{previous_output}\n\n"
    "A reviewer left the following feedback. Rewrite the draft to address it:\n\n{feedback_text}"
)

REWRITE_HUMANIZE_USER_TEMPLATE = (
    "Current humanized version:\n\n{previous_output}\n\n"
    "A reviewer left the following feedback. Rewrite it to address the feedback:\n\n{feedback_text}"
)


class BlogPostOutlinePrompt(BaseGenerateTextPrompt):
    """Outline: the shape of the post, before anything writes prose."""

    def build_generate_prompt(self, state: GenerateTextState) -> BuildPromptResult:
        user_prompt = OUTLINE_USER_TEMPLATE.format(
            prompt_text=state.prompt_text
        ) + self._build_additional_context_section(state.additional_context)
        return BuildPromptResult(
            system_prompt=self._build_system_prompt(state), user_prompt=user_prompt
        )

    def build_rewrite_prompt(
        self, state: GenerateTextState, previous_output: str, feedback_text: str
    ) -> BuildPromptResult:
        user_prompt = REWRITE_OUTLINE_USER_TEMPLATE.format(
            prompt_text=state.prompt_text,
            previous_output=previous_output,
            feedback_text=feedback_text,
        )
        return BuildPromptResult(
            system_prompt=self._build_system_prompt(state), user_prompt=user_prompt
        )

    def _build_system_prompt(self, state: GenerateTextState) -> str:
        persona = state.build_persona()
        persona_section = self._build_persona_section(
            persona, ["name", "bio", "background", "expertise"]
        )
        tone_and_audience_section = self._build_tone_and_audience_section(
            state.tone, state.target_audience
        )
        return OUTLINE_SYSTEM_PROMPT + persona_section + tone_and_audience_section


class BlogPostDraftPrompt(BaseGenerateTextPrompt):
    """Draft: always runs. A blog post without a draft isn't one."""

    def build_generate_prompt(self, state: GenerateTextState) -> BuildPromptResult:
        user_prompt = DRAFT_USER_TEMPLATE.format(
            outline_text=state.latest_output(), prompt_text=state.prompt_text
        ) + self._build_additional_context_section(state.additional_context)
        return BuildPromptResult(
            system_prompt=self._build_system_prompt(state), user_prompt=user_prompt
        )

    def build_rewrite_prompt(
        self, state: GenerateTextState, previous_output: str, feedback_text: str
    ) -> BuildPromptResult:
        user_prompt = REWRITE_DRAFT_USER_TEMPLATE.format(
            prompt_text=state.prompt_text,
            previous_output=previous_output,
            feedback_text=feedback_text,
        )
        return BuildPromptResult(
            system_prompt=self._build_system_prompt(state), user_prompt=user_prompt
        )

    def _build_system_prompt(self, state: GenerateTextState) -> str:
        persona = state.build_persona()
        persona_section = self._build_persona_section(
            persona,
            ["name", "bio", "background", "expertise", "writing_style", "sample_writing"],
        )
        tone_and_audience_section = self._build_tone_and_audience_section(
            state.tone, state.target_audience
        )
        return DRAFT_SYSTEM_PROMPT + persona_section + tone_and_audience_section


class BlogPostHumanizePrompt(BaseGenerateTextPrompt):
    """Humanize: a last pass over the draft, when the caller asked for one."""

    def build_generate_prompt(self, state: GenerateTextState) -> BuildPromptResult:
        user_prompt = HUMANIZE_USER_TEMPLATE.format(
            draft_text=state.latest_output()
        ) + self._build_additional_context_section(state.additional_context)
        return BuildPromptResult(
            system_prompt=self._build_system_prompt(state), user_prompt=user_prompt
        )

    def build_rewrite_prompt(
        self, state: GenerateTextState, previous_output: str, feedback_text: str
    ) -> BuildPromptResult:
        user_prompt = REWRITE_HUMANIZE_USER_TEMPLATE.format(
            previous_output=previous_output, feedback_text=feedback_text
        )
        return BuildPromptResult(
            system_prompt=self._build_system_prompt(state), user_prompt=user_prompt
        )

    def _build_system_prompt(self, state: GenerateTextState) -> str:
        persona = state.build_persona()
        persona_section = self._build_persona_section(
            persona, ["name", "writing_style", "sample_writing"]
        )
        tone_and_audience_section = self._build_tone_and_audience_section(
            state.tone, state.target_audience
        )
        return HUMANIZE_SYSTEM_PROMPT + persona_section + tone_and_audience_section
