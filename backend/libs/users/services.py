from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from libs.database.orm import UserAuthProviderOrm, UserOrm
from libs.users.inputs import FindOrCreateUserFromAuthProviderInput
from libs.users.results import FindOrCreateUserFromAuthProviderResult, FindUserByIdentityResult


class UserService:
    def __init__(self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    async def find_or_create_user_from_auth_provider(
        self,
        find_or_create_user_from_auth_provider_input: FindOrCreateUserFromAuthProviderInput,
    ) -> FindOrCreateUserFromAuthProviderResult:
        user_auth_provider_query = select(UserAuthProviderOrm).where(
            UserAuthProviderOrm.provider == find_or_create_user_from_auth_provider_input.provider,
            UserAuthProviderOrm.provider_subject
            == find_or_create_user_from_auth_provider_input.provider_subject,
        )
        user_auth_provider_query_result = await self._db_session.execute(user_auth_provider_query)
        user_auth_provider_orm = user_auth_provider_query_result.scalar_one_or_none()

        if user_auth_provider_orm is not None:
            existing_user_query = select(UserOrm).where(
                UserOrm.id == user_auth_provider_orm.user_id
            )
            existing_user_query_result = await self._db_session.execute(existing_user_query)
            existing_user_orm = existing_user_query_result.scalar_one_or_none()

            if existing_user_orm is None:
                raise ForbiddenException("User account is not available")
            if not existing_user_orm.is_active:
                raise ForbiddenException("User account is inactive")

            return FindOrCreateUserFromAuthProviderResult(
                id=existing_user_orm.id, identity=existing_user_orm.identity, is_new_user=False
            )

        email_match_query = select(UserOrm).where(
            UserOrm.email == find_or_create_user_from_auth_provider_input.email
        )
        email_match_query_result = await self._db_session.execute(email_match_query)
        email_match_user_orm = email_match_query_result.scalar_one_or_none()

        if email_match_user_orm is not None:
            raise ConflictException("An account with this email already exists")

        user_orm = UserOrm(
            email=find_or_create_user_from_auth_provider_input.email,
            is_email_verified=find_or_create_user_from_auth_provider_input.is_email_verified,
            display_name=find_or_create_user_from_auth_provider_input.display_name,
            avatar_url=find_or_create_user_from_auth_provider_input.avatar_url,
        )
        self._db_session.add(user_orm)
        await self._db_session.flush()

        user_auth_provider_orm = UserAuthProviderOrm(
            user_id=user_orm.id,
            provider=find_or_create_user_from_auth_provider_input.provider,
            provider_subject=find_or_create_user_from_auth_provider_input.provider_subject,
            email_at_provider=find_or_create_user_from_auth_provider_input.email,
            created_by_id=user_orm.id,
            updated_by_id=user_orm.id,
        )
        self._db_session.add(user_auth_provider_orm)
        await self._db_session.flush()

        return FindOrCreateUserFromAuthProviderResult(
            id=user_orm.id, identity=user_orm.identity, is_new_user=True
        )

    async def find_user_by_identity(self, user_identity: UUID) -> FindUserByIdentityResult:
        query = select(UserOrm).where(UserOrm.identity == user_identity)
        query_result = await self._db_session.execute(query)
        user_orm = query_result.scalar_one_or_none()

        if user_orm is None:
            raise NotFoundException("User not found")
        return FindUserByIdentityResult.model_validate(user_orm)
