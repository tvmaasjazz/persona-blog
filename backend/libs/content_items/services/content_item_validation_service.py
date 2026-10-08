from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.auth.results import AuthUser
from libs.content_items.exceptions import (
    ContentItemGenerateTextRunAlreadySavedException,
    ContentItemGenerateTextRunNotCompletedException,
    ContentItemPersonaPrivateException,
)
from libs.core.exceptions import NotFoundException
from libs.database.orm import GenerateTextRunOrm, PersonaOrm
from libs.generate_text.types import GenerateTextRunStatusType


class ContentItemValidationService:
    def __init__(self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    async def validate_persona_allows_public(
        self, persona_identity: UUID, is_public: bool, auth_user: AuthUser
    ) -> None:
        if not is_public:
            return

        persona_query = select(PersonaOrm).where(
            PersonaOrm.identity == persona_identity,
            PersonaOrm.created_by_id == auth_user.id,
        )
        persona_query_result = await self._db_session.execute(persona_query)
        persona_record = persona_query_result.scalar_one_or_none()

        if persona_record is None:
            return
        if not persona_record.is_public:
            raise ContentItemPersonaPrivateException(
                "A private persona's content can't be made public"
            )

    async def validate_generate_text_run_available(
        self, generate_text_run_identity: UUID, auth_user: AuthUser
    ) -> None:
        run_query = select(GenerateTextRunOrm).where(
            GenerateTextRunOrm.identity == generate_text_run_identity,
            GenerateTextRunOrm.created_by_id == auth_user.id,
        )
        run_query_result = await self._db_session.execute(run_query)
        generate_text_run_record = run_query_result.scalar_one_or_none()

        if generate_text_run_record is None:
            raise NotFoundException("Generate text run not found")
        if generate_text_run_record.status != GenerateTextRunStatusType.COMPLETED:
            raise ContentItemGenerateTextRunNotCompletedException(
                "Generate text run is not completed"
            )
        if generate_text_run_record.content_item_id is not None:
            raise ContentItemGenerateTextRunAlreadySavedException(
                "Generate text run is already saved to a content item"
            )

    async def validate_generate_text_run_allows_public(
        self, generate_text_run_identity: UUID, is_public: bool, auth_user: AuthUser
    ) -> None:
        if not is_public:
            return

        persona_is_public_query = (
            select(PersonaOrm.is_public)
            .select_from(GenerateTextRunOrm)
            .join(PersonaOrm, GenerateTextRunOrm.persona_id == PersonaOrm.id)
            .where(
                GenerateTextRunOrm.identity == generate_text_run_identity,
                GenerateTextRunOrm.created_by_id == auth_user.id,
            )
        )
        persona_is_public_query_result = await self._db_session.execute(persona_is_public_query)
        persona_is_public = persona_is_public_query_result.scalar_one_or_none()

        if persona_is_public is None:
            return
        if not persona_is_public:
            raise ContentItemPersonaPrivateException(
                "A private persona's content can't be made public"
            )
