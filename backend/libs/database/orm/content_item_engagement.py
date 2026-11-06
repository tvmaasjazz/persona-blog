from sqlalchemy import BigInteger, Double, ForeignKey, Index, Integer, text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from libs.database.base import BaseOrm
from libs.database.orm.content_item import ContentItemOrm


class ContentItemEngagementOrm(BaseOrm):
    __tablename__ = "pb_content_item_engagement"
    __table_args__ = (
        Index(
            "pb_content_item_engagement_feed_score_idx",
            text("feed_score DESC NULLS LAST"),
        ),
    )

    content_item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey(ContentItemOrm.id, ondelete="CASCADE"), unique=True
    )
    view_count: Mapped[int] = mapped_column(Integer, server_default=text("0"))
    read_percent_sum: Mapped[int] = mapped_column(BigInteger, server_default=text("0"))
    feed_score: Mapped[float | None] = mapped_column(Double)

    content_item: Mapped[ContentItemOrm] = relationship()
