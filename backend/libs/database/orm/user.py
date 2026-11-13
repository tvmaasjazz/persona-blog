from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, ForeignKey, Index, Numeric, false, text, true
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from libs.database.base import BaseOrm
from libs.database.orm.role import RoleOrm


class UserOrm(BaseOrm):
    __tablename__ = "psg_user"
    __table_args__ = (
        Index(
            "psg_user_email_idx", "email", unique=True, postgresql_where=text("deleted_at IS NULL")
        ),
        Index(
            "psg_user_is_system_user_idx",
            "is_system_user",
            unique=True,
            postgresql_where=text("is_system_user"),
        ),
    )

    email: Mapped[str] = mapped_column(CITEXT)
    is_email_verified: Mapped[bool] = mapped_column(server_default=false())
    display_name: Mapped[str | None]
    avatar_url: Mapped[str | None]
    is_active: Mapped[bool] = mapped_column(server_default=true())
    is_system_user: Mapped[bool] = mapped_column(server_default=false())
    last_login_at: Mapped[datetime | None]
    last_activity_at: Mapped[datetime | None]
    credit_balance_usd: Mapped[Decimal] = mapped_column(Numeric(16, 10), server_default=text("0"))
    role_id: Mapped[int] = mapped_column(BigInteger, ForeignKey(RoleOrm.id))

    # A person signing up has no creator, so psg_user relaxes BaseOrm's audit columns.
    created_by_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("psg_user.id"))
    updated_by_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("psg_user.id"))
