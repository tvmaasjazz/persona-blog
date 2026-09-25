from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import BigInteger, Enum, ForeignKey, Index, Integer, Numeric, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from libs.database.base import BaseOrm
from libs.database.orm.generate_text_run import GenerateTextRunOrm
from libs.database.orm.user import UserOrm
from libs.generate_text.types import GenerateTextStepStatusType, HumanDecisionType


class GenerateTextStepOrm(BaseOrm):
    __tablename__ = "pb_generate_text_step"
    __table_args__ = (
        UniqueConstraint("run_id", "seq", name="pb_generate_text_step_run_id_seq_key"),
        Index("pb_generate_text_step_run_id_seq_idx", "run_id", "seq"),
    )

    run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey(GenerateTextRunOrm.id, ondelete="CASCADE")
    )
    seq: Mapped[int] = mapped_column(Integer)
    step_name: Mapped[str]
    attempt: Mapped[int] = mapped_column(Integer, server_default=text("1"))
    status: Mapped[GenerateTextStepStatusType] = mapped_column(
        Enum(GenerateTextStepStatusType, name="pb_generate_text_step_status_type")
    )
    input: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    llm_call_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    input_tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    output_tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(16, 10), server_default=text("0"))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    human_decision: Mapped[HumanDecisionType | None] = mapped_column(
        Enum(HumanDecisionType, name="pb_human_decision_type")
    )
    human_feedback: Mapped[str | None]
    decided_by_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey(UserOrm.id))
    decided_at: Mapped[datetime | None]
    error_code: Mapped[str | None]
    error_message: Mapped[str | None]
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]

    run: Mapped[GenerateTextRunOrm] = relationship(back_populates="steps")
