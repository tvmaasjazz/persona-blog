from decimal import Decimal
from typing import Any

from sqlalchemy import Enum, Index, Integer, Numeric, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from libs.database.base import BaseOrm
from libs.llm.types import LlmCallReasonType, LlmCallStatusType, LlmProviderType, LlmType


class LlmCallOrm(BaseOrm):
    __tablename__ = "pb_llm_call"
    __table_args__ = (Index("pb_llm_call_created_by_id_idx", "created_by_id"),)

    llm_type: Mapped[LlmType] = mapped_column(Enum(LlmType, name="pb_llm_type"))
    provider: Mapped[LlmProviderType] = mapped_column(
        Enum(LlmProviderType, name="pb_llm_provider_type")
    )
    model_name: Mapped[str]
    purpose: Mapped[str]
    system_prompt: Mapped[str | None]
    user_prompt: Mapped[str]
    response_text: Mapped[str | None]
    response_json: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    reason: Mapped[LlmCallReasonType | None] = mapped_column(
        Enum(LlmCallReasonType, name="pb_llm_call_reason_type")
    )
    status: Mapped[LlmCallStatusType] = mapped_column(
        Enum(LlmCallStatusType, name="pb_llm_call_status_type"),
        server_default=text("'PENDING'"),
    )
    input_tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    output_tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    cached_input_tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    reasoning_tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(12, 6), server_default=text("0"))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None]
    error_message: Mapped[str | None]
    provider_request_reference: Mapped[str | None]
