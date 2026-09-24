from uuid import UUID

from pydantic import BaseModel

from libs.generate_text.inputs import GenerateTextInput, ResumeGenerateTextInput
from libs.generate_text.results import GenerateTextResult
from libs.generate_text.types import GenerateTextStatusType, TextType


class GenerateTextDto(BaseModel):
    text_type: TextType
    prompt_text: str

    def to_input(self) -> GenerateTextInput:
        return GenerateTextInput(text_type=self.text_type, prompt_text=self.prompt_text)


class ResumeGenerateTextDto(BaseModel):
    is_approved: bool
    feedback_text: str | None

    def to_input(self) -> ResumeGenerateTextInput:
        return ResumeGenerateTextInput(
            is_approved=self.is_approved, feedback_text=self.feedback_text
        )


class GeneratedTextResponseDto(BaseModel):
    thread_identity: UUID
    status: GenerateTextStatusType
    content: str
    character_count: int

    @classmethod
    def from_result(cls, result: GenerateTextResult) -> GeneratedTextResponseDto:
        return cls(
            thread_identity=result.thread_identity,
            status=result.status,
            content=result.content,
            character_count=result.character_count,
        )
