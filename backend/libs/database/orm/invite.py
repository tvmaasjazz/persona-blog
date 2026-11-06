from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Numeric, desc
from sqlalchemy.orm import Mapped, mapped_column

from libs.database.base import BaseOrm
from libs.database.orm.user import UserOrm


class InviteOrm(BaseOrm):
    __tablename__ = "pb_invite"
    __table_args__ = (
        CheckConstraint("(used_at IS NULL) = (used_by_user_id IS NULL)", name="used"),
        CheckConstraint("used_at IS NULL OR revoked_at IS NULL", name="used_revoked"),
        Index("pb_invite_created_at_idx", desc("created_at")),
    )

    name: Mapped[str]
    credit_amount_usd: Mapped[Decimal] = mapped_column(
        Numeric(16, 10), CheckConstraint("credit_amount_usd > 0", name="credit_amount_usd")
    )
    note: Mapped[str | None]
    code_hash: Mapped[str] = mapped_column(unique=True)
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]
    used_by_user_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey(UserOrm.id))
    revoked_at: Mapped[datetime | None]
