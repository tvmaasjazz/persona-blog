from abc import ABC, abstractmethod

from libs.generate_text.inputs import GenerateTextPersonaInput
from libs.generate_text.results import BuildPromptResult
from libs.generate_text.states import GenerateTextState

PERSONA_FIELD_LABELS: dict[str, str] = {
    "name": "Name",
    "bio": "Bio",
    "background": "Background",
    "expertise": "Expertise",
    "writing_style": "Writing style",
    "sample_writing": "Sample writing",
}

PROMPT_LINE_TEMPLATE = "{label}: {value}"
PERSONA_PROMPT_SECTION_TEMPLATE = "\n\nWho you are writing as:\n{persona_lines}"
TONE_AND_AUDIENCE_PROMPT_SECTION_TEMPLATE = "\n\nFor this piece:\n{tone_and_audience_lines}"
ADDITIONAL_CONTEXT_PROMPT_SECTION_TEMPLATE = "\n\nAdditional context:\n\n{additional_context}"


class BaseGenerateTextPrompt(ABC):
    @abstractmethod
    def build_generate_prompt(self, state: GenerateTextState) -> BuildPromptResult: ...

    @abstractmethod
    def build_rewrite_prompt(
        self, state: GenerateTextState, previous_output: str, feedback_text: str
    ) -> BuildPromptResult: ...

    def _build_persona_prompt_section(
        self, persona: GenerateTextPersonaInput, field_names: list[str]
    ) -> str:
        persona_lines = [
            PROMPT_LINE_TEMPLATE.format(label=PERSONA_FIELD_LABELS[field_name], value=field_value)
            for field_name in field_names
            if (field_value := getattr(persona, field_name))
        ]
        if not persona_lines:
            return ""
        return PERSONA_PROMPT_SECTION_TEMPLATE.format(persona_lines="\n".join(persona_lines))

    def _build_tone_and_audience_prompt_section(
        self, tone: str | None, target_audience: str | None
    ) -> str:
        tone_and_audience_lines = [
            PROMPT_LINE_TEMPLATE.format(label=label, value=value)
            for label, value in (("Tone", tone), ("Target audience", target_audience))
            if value
        ]
        if not tone_and_audience_lines:
            return ""
        return TONE_AND_AUDIENCE_PROMPT_SECTION_TEMPLATE.format(
            tone_and_audience_lines="\n".join(tone_and_audience_lines)
        )

    def _build_additional_context_prompt_section(self, additional_context: str | None) -> str:
        if not additional_context:
            return ""
        return ADDITIONAL_CONTEXT_PROMPT_SECTION_TEMPLATE.format(
            additional_context=additional_context
        )
