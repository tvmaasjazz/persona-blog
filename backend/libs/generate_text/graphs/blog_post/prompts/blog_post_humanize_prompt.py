from libs.generate_text.graphs.blog_post.blog_post_body_output_format import (
    BLOG_POST_BODY_FORMAT_RULES,
)
from libs.generate_text.prompts import BaseGenerateTextPrompt
from libs.generate_text.results import BuildPromptResult
from libs.generate_text.states import GenerateTextState

HUMANIZE_SYSTEM_TEMPLATE = (
    "Rewrite the given blog post draft so it reads like a person wrote it: vary "
    "sentence rhythm, cut filler and hedging, and remove anything that reads as "
    "AI-generated, while keeping the meaning and structure intact.\n\n{format_rules}"
    "{persona_prompt_section}{tone_and_audience_prompt_section}"
)

HUMANIZE_USER_TEMPLATE = "Draft:\n\n{draft_text}{additional_context_prompt_section}"

HUMANIZE_REWRITE_USER_TEMPLATE = (
    "Current humanized version:\n\n{previous_output}\n\n"
    "A reviewer left the following feedback. Rewrite it to address the feedback:\n\n{feedback_text}"
)


class BlogPostHumanizePrompt(BaseGenerateTextPrompt):
    def build_generate_prompt(self, state: GenerateTextState) -> BuildPromptResult:
        additional_context_prompt_section = self._build_additional_context_prompt_section(
            state.additional_context
        )
        user_prompt = HUMANIZE_USER_TEMPLATE.format(
            draft_text=state.latest_output(),
            additional_context_prompt_section=additional_context_prompt_section,
        )
        return BuildPromptResult(
            system_prompt=self._build_system_prompt(state), user_prompt=user_prompt
        )

    def build_rewrite_prompt(
        self, state: GenerateTextState, previous_output: str, feedback_text: str
    ) -> BuildPromptResult:
        user_prompt = HUMANIZE_REWRITE_USER_TEMPLATE.format(
            previous_output=previous_output,
            feedback_text=feedback_text,
        )
        return BuildPromptResult(
            system_prompt=self._build_system_prompt(state), user_prompt=user_prompt
        )

    def _build_system_prompt(self, state: GenerateTextState) -> str:
        persona = state.build_persona()
        persona_prompt_section = self._build_persona_prompt_section(
            persona, ["name", "writing_style", "sample_writing"]
        )
        tone_and_audience_prompt_section = self._build_tone_and_audience_prompt_section(
            state.tone, state.target_audience
        )
        return HUMANIZE_SYSTEM_TEMPLATE.format(
            format_rules=BLOG_POST_BODY_FORMAT_RULES,
            persona_prompt_section=persona_prompt_section,
            tone_and_audience_prompt_section=tone_and_audience_prompt_section,
        )
