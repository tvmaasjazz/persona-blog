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
    last_step: str | None
    graph_name: str
    graph_version: str
    persona_identity: UUID | None
    prompt_text: str
    tone: str | None
    target_audience: str | None
    additional_context: str | None
    options: dict[str, Any]
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
    prompt_text: str
    tone: str | None
    target_audience: str | None
    additional_context: str | None
    options: dict[str, Any]
    persona_id: int | None
    persona_identity: UUID | None = None
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


class FindLatestGenerateTextStepResult(BaseModel):
    """The run's newest step: where it sits, and the text it produced."""

    step_name: str
    content: str


class BuildPromptResult(BaseModel):
    system_prompt: str
    user_prompt: str


class ValidateOutputResult(BaseModel):
    error_messages: list[str]
