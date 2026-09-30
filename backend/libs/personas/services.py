from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.auth.results import AuthUser
from libs.core.exceptions import ForbiddenException, NotFoundException
from libs.database.orm import PersonaOrm
from libs.personas.exceptions import PersonaNameTakenException
from libs.personas.inputs import PersonaInput
from libs.personas.results import CreatePersonaResult, ListPersonasResult, PersonaDetailResult


class PersonaService:
    def __init__(self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    async def create_persona(
        self, persona_input: PersonaInput, auth_user: AuthUser
    ) -> CreatePersonaResult:
        persona_record = PersonaOrm(
            name=persona_input.name,
            bio=persona_input.bio,
            avatar_url=persona_input.avatar_url,
            background=persona_input.background,
            expertise=persona_input.expertise,
            writing_style=persona_input.writing_style,
            default_tone=persona_input.default_tone,
            default_target_audience=persona_input.default_target_audience,
            sample_writing=persona_input.sample_writing,
            is_public=persona_input.is_public,
            created_by_id=auth_user.id,
            updated_by_id=auth_user.id,
        )
        self._db_session.add(persona_record)
        await self._db_session.flush()

        return CreatePersonaResult(identity=persona_record.identity)

    async def find_persona(
        self, persona_identity: UUID, auth_user: AuthUser
    ) -> PersonaDetailResult:
        persona_record = await self._find_visible_persona_record(persona_identity, auth_user)
        return PersonaDetailResult.model_validate(persona_record, from_attributes=True)

    async def list_personas(self, auth_user: AuthUser) -> ListPersonasResult:
        persona_query = (
            select(PersonaOrm)
            .where(PersonaOrm.created_by_id == auth_user.id)
            .order_by(PersonaOrm.created_at.desc())
        )
        persona_query_result = await self._db_session.execute(persona_query)
        persona_records = persona_query_result.scalars().all()

        return ListPersonasResult(
            personas=[
                PersonaDetailResult.model_validate(persona_record, from_attributes=True)
                for persona_record in persona_records
            ]
        )

    async def update_persona(
        self, persona_identity: UUID, persona_input: PersonaInput, auth_user: AuthUser
    ) -> None:
        persona_record = await self._find_owned_persona_record(persona_identity, auth_user)
        persona_record.name = persona_input.name
        persona_record.bio = persona_input.bio
        persona_record.avatar_url = persona_input.avatar_url
        persona_record.background = persona_input.background
        persona_record.expertise = persona_input.expertise
        persona_record.writing_style = persona_input.writing_style
        persona_record.default_tone = persona_input.default_tone
        persona_record.default_target_audience = persona_input.default_target_audience
        persona_record.sample_writing = persona_input.sample_writing
        persona_record.is_public = persona_input.is_public
        persona_record.updated_by_id = auth_user.id
        await self._db_session.flush()

    async def delete_persona(self, persona_identity: UUID, auth_user: AuthUser) -> None:
        persona_record = await self._find_owned_persona_record(persona_identity, auth_user)
        persona_record.deleted_at = datetime.now(UTC)
        persona_record.deleted_by_id = auth_user.id
        await self._db_session.flush()

    async def ensure_persona_name_available(
        self, persona_name: str, auth_user: AuthUser, persona_identity: UUID | None = None
    ) -> None:
        """Raises PersonaNameTakenException when the caller already has a live persona with
        this name. persona_identity is the persona being renamed, which keeps its own name."""
        persona_query = select(PersonaOrm.id).where(
            PersonaOrm.created_by_id == auth_user.id,
            PersonaOrm.name == persona_name,
        )
        if persona_identity is not None:
            persona_query = persona_query.where(PersonaOrm.identity != persona_identity)
        persona_query_result = await self._db_session.execute(persona_query)

        if persona_query_result.first() is not None:
            raise PersonaNameTakenException("You already have a persona with this name")

    async def _find_visible_persona_record(
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
        persona_record = await self._find_visible_persona_record(persona_identity, auth_user)
        if persona_record.created_by_id != auth_user.id:
            raise ForbiddenException("Only the persona's creator can change it")
        return persona_record
