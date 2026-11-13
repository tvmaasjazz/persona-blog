from datetime import date

from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, SmallInteger, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from libs.database.base import BaseOrm
from libs.database.orm.content_item import ContentItemOrm
from libs.database.orm.user import UserOrm


class ContentItemViewOrm(BaseOrm):
    __tablename__ = "psg_content_item_view"
    __table_args__ = (
        CheckConstraint(
            "(created_by_id IS NULL) <> (anonymous_user_key IS NULL)",
            name="viewer",
        ),
        Index(
            "psg_content_item_view_user_viewer_day_idx",
            "content_item_id",
            "created_by_id",
            "viewed_on",
            unique=True,
            postgresql_where=text("created_by_id IS NOT NULL AND deleted_at IS NULL"),
        ),
        Index(
            "psg_content_item_view_anonymous_viewer_day_idx",
            "content_item_id",
            "anonymous_user_key",
            "viewed_on",
            unique=True,
            postgresql_where=text("anonymous_user_key IS NOT NULL AND deleted_at IS NULL"),
        ),
    )

    content_item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey(ContentItemOrm.id, ondelete="CASCADE")
    )
    viewed_on: Mapped[date] = mapped_column(
        server_default=text("((now() AT TIME ZONE 'utc')::date)")
    )
    read_percent: Mapped[int] = mapped_column(
        SmallInteger,
        CheckConstraint(
            "read_percent IN (0, 25, 50, 75, 100)",
            name="read_percent",
        ),
    )
    anonymous_user_key: Mapped[str | None]

    # A signed-out visitor's view has no user, so the audit columns are nullable
    # (database.md, Shared columns)
    created_by_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey(UserOrm.id))
    updated_by_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey(UserOrm.id))

    content_item: Mapped[ContentItemOrm] = relationship()
