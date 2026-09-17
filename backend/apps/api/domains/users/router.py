from fastapi import APIRouter

from apps.api.core.dependencies import AuthUserDep
from apps.api.domains.users.dependencies import UserServiceDep
from apps.api.domains.users.dtos import UserResponseDto

user_router = APIRouter(prefix="/users", tags=["users"])


@user_router.get("/me")
async def find_signed_in_user(
    auth_user: AuthUserDep, user_service: UserServiceDep
) -> UserResponseDto:
    find_user_by_identity_result = await user_service.find_user_by_identity(auth_user.identity)
    return UserResponseDto.from_result(find_user_by_identity_result)
