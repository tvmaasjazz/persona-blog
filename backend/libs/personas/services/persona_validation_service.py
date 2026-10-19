from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.auth.results import AuthUser
from libs.database.orm import PersonaOrm
from libs.personas.exceptions import PersonaNameTakenException


class PersonaValidationService:
    """The checks on an incoming persona payload that need the database."""

    def __init__(self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    async def validate_persona_name_available(
        self, persona_name: str, auth_user: AuthUser, persona_identity: UUID | None = None
    ) -> None:
        """Raises when the user has another persona with this name, ignoring persona_identity."""
        persona_query = select(PersonaOrm.id).where(
            PersonaOrm.created_by_id == auth_user.id,
            PersonaOrm.name == persona_name,
        )
        if persona_identity is not None:
            persona_query = persona_query.where(PersonaOrm.identity != persona_identity)
        persona_query_result = await self._db_session.execute(persona_query)

        if persona_query_result.first() is not None:
            raise PersonaNameTakenException("You already have a persona with this name")
