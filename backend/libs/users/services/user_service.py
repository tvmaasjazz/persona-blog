from uuid import UUID

from sqlalchemy import insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.core.exceptions import ConflictException, ForbiddenException, NotFoundException
from libs.database.orm import UserAuthProviderOrm, UserOrm
from libs.users.inputs import FindOrCreateUserFromAuthProviderInput
from libs.users.results import FindOrCreateUserFromAuthProviderResult, FindUserByIdentityResult


class UserService:
    """Finds users and creates them on first sign-in through an auth provider."""

    def __init__(self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    async def find_or_create_user_from_auth_provider(
        self,
        find_or_create_user_from_auth_provider_input: FindOrCreateUserFromAuthProviderInput,
    ) -> FindOrCreateUserFromAuthProviderResult:
        """The provider's user, created if new; ForbiddenException if inactive, and
        ConflictException if another account already uses the email."""
        try:
            return await self._find_user_from_auth_provider(
                find_or_create_user_from_auth_provider_input
            )
        except NotFoundException:
            return await self._create_user_from_auth_provider(
                find_or_create_user_from_auth_provider_input
            )

    async def find_user_by_identity(self, user_identity: UUID) -> FindUserByIdentityResult:
        """The user with this identity, active or not; NotFoundException if there is none."""
        user_query = select(UserOrm).where(UserOrm.identity == user_identity)
        user_query_result = await self._db_session.execute(user_query)
        user_record = user_query_result.scalar_one_or_none()

        if user_record is None:
            raise NotFoundException("User not found")
        return FindUserByIdentityResult.model_validate(user_record, from_attributes=True)

    async def _find_user_from_auth_provider(
        self,
        find_or_create_user_from_auth_provider_input: FindOrCreateUserFromAuthProviderInput,
    ) -> FindOrCreateUserFromAuthProviderResult:
        user_auth_provider_query = select(UserAuthProviderOrm).where(
            UserAuthProviderOrm.provider == find_or_create_user_from_auth_provider_input.provider,
            UserAuthProviderOrm.provider_subject
            == find_or_create_user_from_auth_provider_input.provider_subject,
        )
        user_auth_provider_query_result = await self._db_session.execute(user_auth_provider_query)
        user_auth_provider_record = user_auth_provider_query_result.scalar_one_or_none()

        if user_auth_provider_record is None:
            raise NotFoundException("Auth provider not found")

        user_query = select(UserOrm).where(UserOrm.id == user_auth_provider_record.user_id)
        user_query_result = await self._db_session.execute(user_query)
        user_record = user_query_result.scalar_one_or_none()

        if user_record is None:
            raise ForbiddenException("User account is not available")
        if not user_record.is_active:
            raise ForbiddenException("User account is inactive")
        return FindOrCreateUserFromAuthProviderResult(
            id=user_record.id,
            identity=user_record.identity,
            user_auth_provider_id=user_auth_provider_record.id,
            is_new_user=False,
        )

    async def _create_user_from_auth_provider(
        self,
        find_or_create_user_from_auth_provider_input: FindOrCreateUserFromAuthProviderInput,
    ) -> FindOrCreateUserFromAuthProviderResult:
        email_owner_query = select(UserOrm).where(
            UserOrm.email == find_or_create_user_from_auth_provider_input.email
        )
        email_owner_query_result = await self._db_session.execute(email_owner_query)
        email_owner_record = email_owner_query_result.scalar_one_or_none()

        if email_owner_record is not None:
            raise ConflictException("An account with this email already exists")

        user_insert = (
            insert(UserOrm)
            .values(
                email=find_or_create_user_from_auth_provider_input.email,
                is_email_verified=find_or_create_user_from_auth_provider_input.is_email_verified,
                display_name=find_or_create_user_from_auth_provider_input.display_name,
                avatar_url=find_or_create_user_from_auth_provider_input.avatar_url,
            )
            .returning(UserOrm.id, UserOrm.identity)
        )
        user_insert_result = await self._db_session.execute(user_insert)
        user_row = user_insert_result.one()

        user_auth_provider_insert = (
            insert(UserAuthProviderOrm)
            .values(
                user_id=user_row.id,
                provider=find_or_create_user_from_auth_provider_input.provider,
                provider_subject=find_or_create_user_from_auth_provider_input.provider_subject,
                email_at_provider=find_or_create_user_from_auth_provider_input.email,
                created_by_id=user_row.id,
                updated_by_id=user_row.id,
            )
            .returning(UserAuthProviderOrm.id)
        )
        user_auth_provider_insert_result = await self._db_session.execute(user_auth_provider_insert)
        user_auth_provider_id = user_auth_provider_insert_result.scalar_one()

        return FindOrCreateUserFromAuthProviderResult(
            id=user_row.id,
            identity=user_row.identity,
            user_auth_provider_id=user_auth_provider_id,
            is_new_user=True,
        )
