from sqlalchemy import Enum
from sqlalchemy.orm import Mapped, mapped_column

from libs.database.base import BaseOrm
from libs.permissions.types import RoleType


class RoleOrm(BaseOrm):
    __tablename__ = "psg_role"

    code: Mapped[RoleType] = mapped_column(Enum(RoleType, name="psg_role_type"), unique=True)
