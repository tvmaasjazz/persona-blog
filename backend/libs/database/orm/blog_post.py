from sqlalchemy import BigInteger, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column, relationship

from libs.database.base import BaseOrm
from libs.database.orm.content_item import ContentItemOrm


class BlogPostOrm(BaseOrm):
    __tablename__ = "pb_blog_post"

    content_item_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey(ContentItemOrm.id, ondelete="CASCADE"), unique=True
    )
    title: Mapped[str]
    subtitle: Mapped[str | None]
    body: Mapped[str]

    content_item: Mapped[ContentItemOrm] = relationship()
