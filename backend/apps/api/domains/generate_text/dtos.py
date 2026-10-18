from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from libs.generate_text.graphs.blog_post.inputs import BlogPostOptionsInput
from libs.generate_text.inputs import (
    GenerateTextInput,
    ResumeGenerateTextInput,
    StepOptionInput,
)
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
    persona_identity: UUID
    tone: str | None = None
    target_audience: str | None = None
    additional_context: str | None = None
    options: BlogPostOptionsDto

    def to_input(self) -> GenerateTextInput[BlogPostOptionsInput]:
        return GenerateTextInput[BlogPostOptionsInput](
            text_type=TextType.BLOG_POST,
            prompt_text=self.prompt_text,
            tone=self.tone,
            target_audience=self.target_audience,
            additional_context=self.additional_context,
            options=self.options.to_input(),
        )


class ResumeGenerateTextDto(BaseModel):
    is_approved: bool
    feedback_text: str | None = None

    def to_input(self) -> ResumeGenerateTextInput:
        return ResumeGenerateTextInput(
            is_approved=self.is_approved, feedback_text=self.feedback_text
        )


class GenerateTextRunResponseDto(BaseModel):
    run_identity: UUID
    text_type: TextType
    status: GenerateTextRunStatusType
    last_step: str | None
    graph_name: str
    graph_version: str
    persona_identity: UUID | None
    prompt_text: str
    tone: str | None
    target_audience: str | None
    additional_context: str | None
    options: BlogPostOptionsDto
    content: str
    character_count: int
    llm_call_count: int
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    started_at: datetime | None
    finished_at: datetime | None
    poll_interval_ms: int

    @classmethod
    def from_result(cls, result: GenerateTextRunResult) -> GenerateTextRunResponseDto:
        return cls(
            run_identity=result.run_identity,
            text_type=result.text_type,
            status=result.status,
            last_step=result.last_step,
            graph_name=result.graph_name,
            graph_version=result.graph_version,
            persona_identity=result.persona_identity,
            prompt_text=result.prompt_text,
            tone=result.tone,
            target_audience=result.target_audience,
            additional_context=result.additional_context,
            options=BlogPostOptionsDto.model_validate(result.options),
            content=result.content,
            character_count=result.character_count,
            llm_call_count=result.llm_call_count,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_usd=result.cost_usd,
            started_at=result.started_at,
            finished_at=result.finished_at,
            poll_interval_ms=result.poll_interval_ms,
        )
