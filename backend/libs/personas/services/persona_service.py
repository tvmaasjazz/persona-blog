from uuid import UUID

from sqlalchemy import insert, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from libs.auth.results import AuthUser
from libs.core.exceptions import ForbiddenException, NotFoundException
from libs.database.orm import PersonaOrm
from libs.database.utils import DatabaseClockUtils
from libs.personas.inputs import PersonaInput
from libs.personas.results import (
    CreatePersonaResult,
    FindUserPersonaListResult,
    FindUserPersonaResult,
    PersonaDetailResult,
)


class PersonaService:
    def __init__(self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    async def create_persona(
        self, persona_input: PersonaInput, auth_user: AuthUser
    ) -> CreatePersonaResult:
        persona_insert = (
            insert(PersonaOrm)
            .values(
                name=persona_input.name,
                bio=persona_input.bio,
                avatar_url=persona_input.avatar_url,
                background=persona_input.background,
                writing_style=persona_input.writing_style,
                default_tone=persona_input.default_tone,
                default_target_audience=persona_input.default_target_audience,
                sample_writing=persona_input.sample_writing,
                is_public=persona_input.is_public,
                created_by_id=auth_user.id,
                updated_by_id=auth_user.id,
            )
            .returning(PersonaOrm.identity)
        )
        persona_insert_result = await self._db_session.execute(persona_insert)
        persona_identity = persona_insert_result.scalar_one()

        return CreatePersonaResult(identity=persona_identity)

    async def find_persona(
        self, persona_identity: UUID, auth_user: AuthUser
    ) -> PersonaDetailResult:
        persona_record = await self._find_accessible_persona_record(persona_identity, auth_user)
        return PersonaDetailResult.model_validate(persona_record, from_attributes=True)

    async def find_user_persona_list(self, auth_user: AuthUser) -> FindUserPersonaListResult:
        persona_query = (
            select(PersonaOrm)
            .where(PersonaOrm.created_by_id == auth_user.id)
            .order_by(PersonaOrm.created_at.desc())
        )
        persona_query_result = await self._db_session.execute(persona_query)
        persona_records = persona_query_result.scalars().all()

        return FindUserPersonaListResult(
            personas=[
                PersonaDetailResult.model_validate(persona_record, from_attributes=True)
                for persona_record in persona_records
            ]
        )

    async def find_user_persona(
        self, persona_identity: UUID, auth_user: AuthUser
    ) -> FindUserPersonaResult:
        """The caller's own live persona only. Anyone else's persona, public or
        private, is not found here, so a caller can only generate text as their own."""
        persona_query = select(PersonaOrm).where(
            PersonaOrm.identity == persona_identity,
            PersonaOrm.created_by_id == auth_user.id,
        )
        persona_query_result = await self._db_session.execute(persona_query)
        persona_record = persona_query_result.scalar_one_or_none()

        if persona_record is None:
            raise NotFoundException("Persona not found")
        return FindUserPersonaResult.model_validate(persona_record, from_attributes=True)

    async def update_persona(
        self, persona_identity: UUID, persona_input: PersonaInput, auth_user: AuthUser
    ) -> None:
        persona_record = await self._find_owned_persona_record(persona_identity, auth_user)
        persona_update = (
            update(PersonaOrm)
            .where(PersonaOrm.id == persona_record.id)
            .values(
                name=persona_input.name,
                bio=persona_input.bio,
                avatar_url=persona_input.avatar_url,
                background=persona_input.background,
                writing_style=persona_input.writing_style,
                default_tone=persona_input.default_tone,
                default_target_audience=persona_input.default_target_audience,
                sample_writing=persona_input.sample_writing,
                is_public=persona_input.is_public,
                updated_by_id=auth_user.id,
            )
        )
        await self._db_session.execute(persona_update)

    async def delete_persona(self, persona_identity: UUID, auth_user: AuthUser) -> None:
        persona_record = await self._find_owned_persona_record(persona_identity, auth_user)
        persona_delete = (
            update(PersonaOrm)
            .where(PersonaOrm.id == persona_record.id)
            .values(
                deleted_at=DatabaseClockUtils.build_utc_now_sql(),
                deleted_by_id=auth_user.id,
            )
        )
        await self._db_session.execute(persona_delete)

    async def _find_accessible_persona_record(
        self, persona_identity: UUID, auth_user: AuthUser
    ) -> PersonaOrm:
        """The caller's own persona, or anyone's public one. A private persona of someone
        else's is not found, so its existence never leaks."""
        persona_query = select(PersonaOrm).where(
            PersonaOrm.identity == persona_identity,
            or_(PersonaOrm.created_by_id == auth_user.id, PersonaOrm.is_public),
        )
        persona_query_result = await self._db_session.execute(persona_query)
        persona_record = persona_query_result.scalar_one_or_none()

        if persona_record is None:
            raise NotFoundException("Persona not found")
        return persona_record

    async def _find_owned_persona_record(
        self, persona_identity: UUID, auth_user: AuthUser
    ) -> PersonaOrm:
        """Only the creator may change a persona. Someone who can see a public persona
        but didn't create it is forbidden."""
        persona_record = await self._find_accessible_persona_record(persona_identity, auth_user)
        if persona_record.created_by_id != auth_user.id:
            raise ForbiddenException("Only the persona's creator can change it")
        return persona_record
