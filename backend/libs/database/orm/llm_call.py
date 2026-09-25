from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Enum, ForeignKey, Index, Integer, Numeric, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from libs.database.base import BaseOrm
from libs.database.orm.generate_text_run import GenerateTextRunOrm
from libs.database.orm.generate_text_step import GenerateTextStepOrm
from libs.llm.types import LlmCallReasonType, LlmCallStatusType, LlmProviderType, LlmType


class LlmCallOrm(BaseOrm):
    __tablename__ = "pb_llm_call"
    __table_args__ = (
        Index("pb_llm_call_created_by_id_idx", "created_by_id"),
        Index("pb_llm_call_run_id_idx", "run_id"),
        Index("pb_llm_call_step_id_idx", "step_id"),
    )

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
    input_tokens: Mapped[int | None] = mapped_column(Integer)
    output_tokens: Mapped[int | None] = mapped_column(Integer)
    cached_input_tokens: Mapped[int | None] = mapped_column(Integer)
    reasoning_tokens: Mapped[int | None] = mapped_column(Integer)
    cost_usd: Mapped[Decimal | None] = mapped_column(Numeric(16, 10))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    error_code: Mapped[str | None]
    error_message: Mapped[str | None]
    provider_error_message: Mapped[str | None]
    provider_request_reference: Mapped[str | None]
    run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey(GenerateTextRunOrm.id, ondelete="SET NULL")
    )
    step_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey(GenerateTextStepOrm.id, ondelete="SET NULL")
    )
