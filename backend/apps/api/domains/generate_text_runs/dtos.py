from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel

from libs.generate_text.inputs import ResumeGenerateTextInput
from libs.generate_text.results import GenerateTextRunResult
from libs.generate_text.types import GenerateTextRunStatusType, TextType


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
    current_step: str | None
    graph_name: str
    graph_version: str
    content: str
    character_count: int
    llm_call_count: int
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def from_result(cls, result: GenerateTextRunResult) -> GenerateTextRunResponseDto:
        return cls(
            run_identity=result.run_identity,
            text_type=result.text_type,
            status=result.status,
            current_step=result.current_step,
            graph_name=result.graph_name,
            graph_version=result.graph_version,
            content=result.content,
            character_count=result.character_count,
            llm_call_count=result.llm_call_count,
            input_tokens=result.input_tokens,
            output_tokens=result.output_tokens,
            cost_usd=result.cost_usd,
            started_at=result.started_at,
            finished_at=result.finished_at,
        )
