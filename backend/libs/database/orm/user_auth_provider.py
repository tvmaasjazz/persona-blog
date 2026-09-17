from datetime import datetime

from sqlalchemy import BigInteger, Enum, ForeignKey, Index, text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from libs.auth.types import AuthProviderType
from libs.database.base import BaseOrm
from libs.database.orm.user import UserOrm


class UserAuthProviderOrm(BaseOrm):
    __tablename__ = "pb_user_auth_provider"
    __table_args__ = (
        Index(
            "pb_user_auth_provider_provider_subject_idx",
            "provider",
            "provider_subject",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index("pb_user_auth_provider_user_id_idx", "user_id"),
    )

    user_id: Mapped[int] = mapped_column(BigInteger, ForeignKey(UserOrm.id, ondelete="CASCADE"))
    provider: Mapped[AuthProviderType] = mapped_column(
        Enum(AuthProviderType, name="pb_auth_provider_type")
    )
    provider_subject: Mapped[str]
    email_at_provider: Mapped[str | None] = mapped_column(CITEXT)
    last_used_at: Mapped[datetime | None]
