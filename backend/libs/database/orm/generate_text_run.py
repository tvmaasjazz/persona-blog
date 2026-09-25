from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum, Index, Integer, Numeric, desc, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from libs.database.base import BaseOrm
from libs.generate_text.types import GenerateTextRunStatusType, TextType

if TYPE_CHECKING:
    from libs.database.orm.generate_text_step import GenerateTextStepOrm


class GenerateTextRunOrm(BaseOrm):
    __tablename__ = "pb_generate_text_run"
    __table_args__ = (
        Index(
            "pb_generate_text_run_created_by_id_created_at_idx",
            "created_by_id",
            desc("created_at"),
        ),
        Index(
            "pb_generate_text_run_status_idx",
            "status",
            postgresql_where=text("status IN ('PENDING', 'RUNNING', 'AWAITING_REVIEW')"),
        ),
    )

    text_type: Mapped[TextType] = mapped_column(Enum(TextType, name="pb_text_type"))
    graph_name: Mapped[str]
    graph_version: Mapped[str]
    thread_id: Mapped[str] = mapped_column(unique=True)
    status: Mapped[GenerateTextRunStatusType] = mapped_column(
        Enum(GenerateTextRunStatusType, name="pb_generate_text_run_status_type"),
        server_default=text("'PENDING'"),
    )
    current_step: Mapped[str | None]
    prompt_text: Mapped[str]
    persona_info: Mapped[str | None]
    additional_context: Mapped[str | None]
    options: Mapped[dict[str, Any]] = mapped_column(JSONB)
    error_code: Mapped[str | None]
    error_message: Mapped[str | None]
    error_step: Mapped[str | None]
    llm_call_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    input_tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    output_tokens: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    cost_usd: Mapped[Decimal] = mapped_column(Numeric(16, 10), server_default=text("0"))
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]

    steps: Mapped[list[GenerateTextStepOrm]] = relationship(back_populates="run")
