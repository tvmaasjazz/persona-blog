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

PERSONA_SECTION_TEMPLATE = "\n\nWho you are writing as:\n{persona_lines}"
ADDITIONAL_CONTEXT_SECTION_TEMPLATE = "\n\nAdditional context:\n\n{additional_context}"


class BaseGenerateTextPrompt(ABC):
    """Builds the system and user prompt for one graph step, shared by every text
    type's steps. A rewrite is a method here rather than a class of its own, so it
    shares its step's system prompt (fastapi-structure.md > Prompts)."""

    @abstractmethod
    def build_generate_prompt(self, state: GenerateTextState) -> BuildPromptResult: ...

    @abstractmethod
    def build_rewrite_prompt(
        self, state: GenerateTextState, previous_output: str, feedback_text: str
    ) -> BuildPromptResult: ...

    def _build_persona_section(
        self, persona: GenerateTextPersonaInput, field_names: list[str]
    ) -> str:
        """Formats whichever of the subclass's chosen fields the persona actually has,
        skipping empty ones."""
        persona_lines = [
            f"{PERSONA_FIELD_LABELS[field_name]}: {field_value}"
            for field_name in field_names
            if (field_value := getattr(persona, field_name))
        ]
        if not persona_lines:
            return ""
        return PERSONA_SECTION_TEMPLATE.format(persona_lines="\n".join(persona_lines))

    def _build_tone_and_audience_section(
        self, tone: str | None, target_audience: str | None
    ) -> str:
        tone_and_audience_lines = []
        if tone:
            tone_and_audience_lines.append(f"Tone: {tone}")
        if target_audience:
            tone_and_audience_lines.append(f"Target audience: {target_audience}")
        if not tone_and_audience_lines:
            return ""
        return "\n" + "\n".join(tone_and_audience_lines)

    def _build_additional_context_section(self, additional_context: str | None) -> str:
        if not additional_context:
            return ""
        return ADDITIONAL_CONTEXT_SECTION_TEMPLATE.format(additional_context=additional_context)
