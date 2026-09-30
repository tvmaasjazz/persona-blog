from typing import Any

from pydantic import BaseModel

from libs.generate_text.types import TextType


class StepOptionInput(BaseModel):
    is_enabled: bool = True
    is_auto_approved: bool = True


class GenerateTextInput[OptionsT: BaseModel](BaseModel):
    text_type: TextType
    prompt_text: str
    tone: str | None = None
    target_audience: str | None = None
    additional_context: str | None = None
    options: OptionsT


class ResumeGenerateTextInput(BaseModel):
    is_approved: bool
    feedback_text: str | None


class CreateGenerateTextRunInput(BaseModel):
    text_type: TextType
    graph_name: str
    graph_version: str
    prompt_text: str
    persona_id: int
    tone: str | None
    target_audience: str | None
    additional_context: str | None
    options: dict[str, Any]


class CreateGenerateTextStepInput(BaseModel):
    run_id: int
    step_name: str
    input: dict[str, Any] | None


class GenerateTextPersonaInput(BaseModel):
    name: str
    bio: str
    background: str | None = None
    expertise: str | None = None
    writing_style: str | None = None
    sample_writing: str | None = None
