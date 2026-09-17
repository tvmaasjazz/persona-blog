from datetime import UTC, datetime
from typing import Any, ClassVar
from uuid import UUID

from sqlalchemy import BigInteger, ForeignKey, Identity, MetaData, Text, Uuid, text
from sqlalchemy.orm import DeclarativeBase, Mapped, declared_attr, mapped_column

from libs.database.column_types import UtcDateTime
from libs.database.constants import NAMING_CONVENTION, UTC_NOW_SQL


class SoftDeleteMixin:
    """Holds deleted_at apart from BaseOrm so session.py's soft-delete rule has a class to target.

    DeclarativeBase doesn't keep mapped attributes on itself, so the rule can't target BaseOrm.
    """

    deleted_at: Mapped[datetime | None] = mapped_column()


class BaseOrm(SoftDeleteMixin, DeclarativeBase):
    """Every table's shared columns. See plans/user-tables.md."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)
    type_annotation_map: ClassVar[dict[Any, Any]] = {str: Text, datetime: UtcDateTime, UUID: Uuid}

    id: Mapped[int] = mapped_column(BigInteger, Identity(always=True), primary_key=True)
    identity: Mapped[UUID] = mapped_column(server_default=text("gen_random_uuid()"), unique=True)
    created_at: Mapped[datetime] = mapped_column(server_default=text(UTC_NOW_SQL))
    updated_at: Mapped[datetime] = mapped_column(
        server_default=text(UTC_NOW_SQL), onupdate=lambda: datetime.now(UTC)
    )

    # The audit columns reference pb_user by name: UserOrm itself extends BaseOrm, so the
    # class can't be imported here.
    @declared_attr
    def created_by_id(cls) -> Mapped[int]:
        return mapped_column(BigInteger, ForeignKey("pb_user.id"))

    @declared_attr
    def updated_by_id(cls) -> Mapped[int]:
        return mapped_column(BigInteger, ForeignKey("pb_user.id"))

    @declared_attr
    def deleted_by_id(cls) -> Mapped[int | None]:
        return mapped_column(BigInteger, ForeignKey("pb_user.id"))
