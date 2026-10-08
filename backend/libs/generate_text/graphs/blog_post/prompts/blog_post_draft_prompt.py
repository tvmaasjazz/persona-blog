from libs.generate_text.graphs.blog_post.blog_post_body_output_format import (
    BLOG_POST_BODY_FORMAT_RULES,
)
from libs.generate_text.prompts import BaseGenerateTextPrompt
from libs.generate_text.results import BuildPromptResult
from libs.generate_text.states import GenerateTextState

DRAFT_SYSTEM_TEMPLATE = (
    "Write a complete blog post draft from the outline and brief provided. Write the "
    "full prose, ready for review — not another outline.\n\n{format_rules}"
    "{persona_prompt_section}{tone_and_audience_prompt_section}"
)

DRAFT_USER_TEMPLATE = (
    "Outline:\n\n{outline_text}\n\nBrief:\n\n{prompt_text}{additional_context_prompt_section}"
)

DRAFT_REWRITE_USER_TEMPLATE = (
    "Brief:\n\n{prompt_text}\n\n"
    "Current draft:\n\n{previous_output}\n\n"
    "A reviewer left the following feedback. Rewrite the draft to address it:\n\n{feedback_text}"
)


class BlogPostDraftPrompt(BaseGenerateTextPrompt):
    def build_generate_prompt(self, state: GenerateTextState) -> BuildPromptResult:
        additional_context_prompt_section = self._build_additional_context_prompt_section(
            state.additional_context
        )
        user_prompt = DRAFT_USER_TEMPLATE.format(
            outline_text=state.latest_output(),
            prompt_text=state.prompt_text,
            additional_context_prompt_section=additional_context_prompt_section,
        )
        return BuildPromptResult(
            system_prompt=self._build_system_prompt(state), user_prompt=user_prompt
        )

    def build_rewrite_prompt(
        self, state: GenerateTextState, previous_output: str, feedback_text: str
    ) -> BuildPromptResult:
        user_prompt = DRAFT_REWRITE_USER_TEMPLATE.format(
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
            persona, ["name", "bio", "background", "writing_style", "sample_writing"]
        )
        tone_and_audience_prompt_section = self._build_tone_and_audience_prompt_section(
            state.tone, state.target_audience
        )
        return DRAFT_SYSTEM_TEMPLATE.format(
            format_rules=BLOG_POST_BODY_FORMAT_RULES,
            persona_prompt_section=persona_prompt_section,
            tone_and_audience_prompt_section=tone_and_audience_prompt_section,
        )
