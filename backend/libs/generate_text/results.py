from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel

from libs.generate_text.types import GenerateTextRunStatusType, TextType


class GenerateTextRunResult(BaseModel):
    """What a run looks like to a caller, whether it was just started, just resumed, or
    simply read. Each domain's ResponseDto projects the fields it exposes."""

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


class CreateGenerateTextRunResult(BaseModel):
    id: int
    identity: UUID


class FindGenerateTextRunByIdentityResult(BaseModel):
    id: int
    identity: UUID
    text_type: TextType
    graph_name: str
    graph_version: str
    status: GenerateTextRunStatusType
    current_step: str | None
    options: dict[str, Any]
    llm_call_count: int
    input_tokens: int
    output_tokens: int
    cost_usd: Decimal
    started_at: datetime | None
    finished_at: datetime | None
    created_by_id: int


class CreateGenerateTextStepResult(BaseModel):
    id: int
    identity: UUID
