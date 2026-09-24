from pydantic import BaseModel

from libs.generate_text.types import TextType


class GenerateTextInput(BaseModel):
    text_type: TextType
    prompt_text: str


class ResumeGenerateTextInput(BaseModel):
    is_approved: bool
    feedback_text: str | None
