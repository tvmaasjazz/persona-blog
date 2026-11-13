from sqlalchemy import Enum
from sqlalchemy.orm import Mapped, mapped_column

from libs.database.base import BaseOrm
from libs.permissions.types import PermissionType


class PermissionOrm(BaseOrm):
    __tablename__ = "psg_permission"

    code: Mapped[PermissionType] = mapped_column(
        Enum(PermissionType, name="psg_permission_type"), unique=True
    )
