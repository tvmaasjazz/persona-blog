from sqlalchemy import Index, desc, false, text
from sqlalchemy.orm import Mapped, mapped_column

from libs.database.base import BaseOrm


class PersonaOrm(BaseOrm):
    __tablename__ = "pb_persona"
    __table_args__ = (
        Index(
            "pb_persona_created_by_id_name_idx",
            "created_by_id",
            "name",
            unique=True,
            postgresql_where=text("deleted_at IS NULL"),
        ),
        Index(
            "pb_persona_created_by_id_created_at_idx",
            "created_by_id",
            desc("created_at"),
        ),
    )

    name: Mapped[str]
    bio: Mapped[str]
    avatar_url: Mapped[str | None]
    background: Mapped[str | None]
    expertise: Mapped[str | None]
    writing_style: Mapped[str | None]
    default_tone: Mapped[str | None]
    default_target_audience: Mapped[str | None]
    sample_writing: Mapped[str | None]
    is_public: Mapped[bool] = mapped_column(server_default=false())
