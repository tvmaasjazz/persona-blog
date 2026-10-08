from libs.generate_text.prompts import BaseGenerateTextPrompt
from libs.generate_text.results import BuildPromptResult
from libs.generate_text.states import GenerateTextState

OUTLINE_SYSTEM_TEMPLATE = (
    "Write an outline for a blog post: the sections it will cover, the key point each "
    "one makes, and the order they build in. Keep it a plan, not the prose itself."
    "{persona_prompt_section}{tone_and_audience_prompt_section}"
)

OUTLINE_USER_TEMPLATE = "Brief:\n\n{prompt_text}{additional_context_prompt_section}"

OUTLINE_REWRITE_USER_TEMPLATE = (
    "Brief:\n\n{prompt_text}\n\n"
    "Current outline:\n\n{previous_output}\n\n"
    "A reviewer left the following feedback. Rewrite the outline to address it:\n\n{feedback_text}"
)


class BlogPostOutlinePrompt(BaseGenerateTextPrompt):
    def build_generate_prompt(self, state: GenerateTextState) -> BuildPromptResult:
        additional_context_prompt_section = self._build_additional_context_prompt_section(
            state.additional_context
        )
        user_prompt = OUTLINE_USER_TEMPLATE.format(
            prompt_text=state.prompt_text,
            additional_context_prompt_section=additional_context_prompt_section,
        )
        return BuildPromptResult(
            system_prompt=self._build_system_prompt(state), user_prompt=user_prompt
        )

    def build_rewrite_prompt(
        self, state: GenerateTextState, previous_output: str, feedback_text: str
    ) -> BuildPromptResult:
        user_prompt = OUTLINE_REWRITE_USER_TEMPLATE.format(
            prompt_text=state.prompt_text,
            previous_output=previous_output,
            feedback_text=feedback_text,
        )
        return BuildPromptResult(
            system_prompt=self._build_system_prompt(state), user_prompt=user_prompt
        )

    def _build_system_prompt(self, state: GenerateTextState) -> str:
        persona = state.build_persona()
        persona_prompt_section = self._build_persona_prompt_section(
            persona, ["name", "bio", "background"]
        )
        tone_and_audience_prompt_section = self._build_tone_and_audience_prompt_section(
            state.tone, state.target_audience
        )
        return OUTLINE_SYSTEM_TEMPLATE.format(
            persona_prompt_section=persona_prompt_section,
            tone_and_audience_prompt_section=tone_and_audience_prompt_section,
        )
