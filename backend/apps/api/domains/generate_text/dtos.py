from uuid import UUID

from pydantic import BaseModel

from libs.blog_post.inputs import BlogPostOptionsInput
from libs.generate_text.inputs import GenerateTextInput, StepOptionInput
from libs.generate_text.results import GenerateTextRunResult
from libs.generate_text.types import GenerateTextRunStatusType, TextType


class StepOptionDto(BaseModel):
    is_enabled: bool = True
    is_auto_approved: bool = True

    def to_input(self) -> StepOptionInput:
        return StepOptionInput(is_enabled=self.is_enabled, is_auto_approved=self.is_auto_approved)


class BlogPostOptionsDto(BaseModel):
    outline: StepOptionDto | None = None
    draft: StepOptionDto = StepOptionDto()
    humanize: StepOptionDto | None = None

    def to_input(self) -> BlogPostOptionsInput:
        return BlogPostOptionsInput(
            outline=self.outline.to_input() if self.outline is not None else None,
            draft=self.draft.to_input(),
            humanize=self.humanize.to_input() if self.humanize is not None else None,
        )


class GenerateBlogPostDto(BaseModel):
    prompt_text: str
    persona_info: str | None = None
    additional_context: str | None = None
    options: BlogPostOptionsDto

    def to_input(self) -> GenerateTextInput[BlogPostOptionsInput]:
        return GenerateTextInput[BlogPostOptionsInput](
            text_type=TextType.BLOG_POST,
            prompt_text=self.prompt_text,
            persona_info=self.persona_info,
            additional_context=self.additional_context,
            options=self.options.to_input(),
        )


class GeneratedTextResponseDto(BaseModel):
    run_identity: UUID
    status: GenerateTextRunStatusType
    current_step: str | None
    content: str
    character_count: int

    @classmethod
    def from_result(cls, result: GenerateTextRunResult) -> GeneratedTextResponseDto:
        return cls(
            run_identity=result.run_identity,
            status=result.status,
            current_step=result.current_step,
            content=result.content,
            character_count=result.character_count,
        )
