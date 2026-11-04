from uuid import UUID

from pydantic import BaseModel

from apps.api.core.dtos import UsdDecimal
from libs.auth.results import AuthUser
from libs.permissions.types import PermissionType, RoleType
from libs.users.results import FindUserByIdentityResult


class UserResponseDto(BaseModel):
    identity: UUID
    email: str
    display_name: str | None
    avatar_url: str | None
    role: RoleType
    permissions: list[PermissionType]
    credit_balance_usd: UsdDecimal
    is_credit_balance_low: bool

    @classmethod
    def from_result(
        cls, find_user_by_identity_result: FindUserByIdentityResult, auth_user: AuthUser
    ) -> UserResponseDto:
        return cls(
            identity=find_user_by_identity_result.identity,
            email=find_user_by_identity_result.email,
            display_name=find_user_by_identity_result.display_name,
            avatar_url=find_user_by_identity_result.avatar_url,
            role=auth_user.role,
            permissions=sorted(auth_user.permissions),
            credit_balance_usd=find_user_by_identity_result.credit_balance_usd,
            is_credit_balance_low=find_user_by_identity_result.is_credit_balance_low,
        )
