from datetime import datetime

from sqlalchemy import BigInteger, Enum, ForeignKey, Index, desc, false
from sqlalchemy.orm import Mapped, mapped_column

from libs.content_items.types import ContentType
from libs.database.base import BaseOrm
from libs.database.orm.persona import PersonaOrm


class ContentItemOrm(BaseOrm):
    __tablename__ = "pb_content_item"
    __table_args__ = (
        Index(
            "pb_content_item_created_by_id_created_at_idx",
            "created_by_id",
            desc("created_at"),
        ),
        Index(
            "pb_content_item_persona_id_created_at_idx",
            "persona_id",
            desc("created_at"),
        ),
    )

    persona_id: Mapped[int] = mapped_column(BigInteger, ForeignKey(PersonaOrm.id))
    content_type: Mapped[ContentType] = mapped_column(Enum(ContentType, name="pb_content_type"))
    is_public: Mapped[bool] = mapped_column(server_default=false())
    published_at: Mapped[datetime | None]
