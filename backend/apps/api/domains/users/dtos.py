from uuid import UUID

from pydantic import BaseModel

from libs.users.results import FindUserByIdentityResult


class UserResponseDto(BaseModel):
    identity: UUID
    email: str
    display_name: str | None
    avatar_url: str | None

    @classmethod
    def from_result(cls, find_user_by_identity_result: FindUserByIdentityResult) -> UserResponseDto:
        return cls(
            identity=find_user_by_identity_result.identity,
            email=find_user_by_identity_result.email,
            display_name=find_user_by_identity_result.display_name,
            avatar_url=find_user_by_identity_result.avatar_url,
        )
