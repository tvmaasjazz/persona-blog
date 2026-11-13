from sqlalchemy import BigInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from libs.database.base import BaseOrm
from libs.database.orm.permission import PermissionOrm
from libs.database.orm.role import RoleOrm


class RolePermissionOrm(BaseOrm):
    __tablename__ = "psg_role_permission"
    __table_args__ = (
        UniqueConstraint(
            "role_id", "permission_id", name="psg_role_permission_role_id_permission_id_key"
        ),
    )

    role_id: Mapped[int] = mapped_column(BigInteger, ForeignKey(RoleOrm.id))
    permission_id: Mapped[int] = mapped_column(BigInteger, ForeignKey(PermissionOrm.id))
