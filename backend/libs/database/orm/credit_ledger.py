from decimal import Decimal

from sqlalchemy import BigInteger, Enum, ForeignKey, Index, Numeric, desc
from sqlalchemy.orm import Mapped, mapped_column

from libs.credits.types import CreditLedgerEntryType
from libs.database.base import BaseOrm
from libs.database.orm.generate_text_run import GenerateTextRunOrm
from libs.database.orm.generate_text_step import GenerateTextStepOrm
from libs.database.orm.user import UserOrm


class CreditLedgerOrm(BaseOrm):
    __tablename__ = "pb_credit_ledger"
    __table_args__ = (
        Index("pb_credit_ledger_user_id_created_at_idx", "user_id", desc("created_at")),
        Index("pb_credit_ledger_generate_text_run_id_idx", "generate_text_run_id"),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey(UserOrm.id))
    amount_usd: Mapped[Decimal] = mapped_column(Numeric(16, 10))
    entry_type: Mapped[CreditLedgerEntryType] = mapped_column(
        Enum(CreditLedgerEntryType, name="pb_credit_ledger_entry_type")
    )
    generate_text_run_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey(GenerateTextRunOrm.id)
    )
    generate_text_step_id: Mapped[int | None] = mapped_column(
        BigInteger, ForeignKey(GenerateTextStepOrm.id)
    )
    note: Mapped[str | None]
