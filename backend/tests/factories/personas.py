from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from libs.core.types import SortDirectionType
from libs.database.orm import PersonaOrm
from libs.personas.inputs import FindUserPersonaPageInput, PersonaInput
from libs.personas.results import FindUserPersonaResult
from libs.personas.types import UserPersonaSortType
from tests.factories.core import build_pagination_input


def build_persona_input(
    *,
    name: str | None = None,
    bio: str = "Writes about coffee and slow mornings.",
    avatar_url: str | None = None,
    background: str | None = None,
    writing_style: str | None = None,
    default_tone: str | None = None,
    default_target_audience: str | None = None,
    sample_writing: str | None = None,
    is_public: bool = False,
) -> PersonaInput:
    return PersonaInput(
        name=name or _build_unique_name(),
        bio=bio,
        avatar_url=avatar_url,
        background=background,
        writing_style=writing_style,
        default_tone=default_tone,
        default_target_audience=default_target_audience,
        sample_writing=sample_writing,
        is_public=is_public,
    )


def build_find_user_persona_page_input(
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    sort_by: UserPersonaSortType = UserPersonaSortType.CREATED_AT,
    sort_direction: SortDirectionType = SortDirectionType.DESC,
) -> FindUserPersonaPageInput:
    return FindUserPersonaPageInput(
        pagination_input=build_pagination_input(
            page=page, page_size=page_size, search=search, sort_direction=sort_direction
        ),
        sort_by=sort_by,
    )


async def insert_persona_row(
    db_session: AsyncSession,
    *,
    created_by_id: int,
    name: str | None = None,
    bio: str = "Writes about coffee and slow mornings.",
    avatar_url: str | None = None,
    background: str | None = None,
    writing_style: str | None = None,
    default_tone: str | None = None,
    default_target_audience: str | None = None,
    sample_writing: str | None = None,
    is_public: bool = False,
    created_at: datetime | None = None,
    deleted_at: datetime | None = None,
    deleted_by_id: int | None = None,
) -> PersonaOrm:
    persona_record = PersonaOrm(
        name=name or _build_unique_name(),
        bio=bio,
        avatar_url=avatar_url,
        background=background,
        writing_style=writing_style,
        default_tone=default_tone,
        default_target_audience=default_target_audience,
        sample_writing=sample_writing,
        is_public=is_public,
        deleted_at=deleted_at,
        created_by_id=created_by_id,
        updated_by_id=created_by_id,
        deleted_by_id=deleted_by_id,
    )
    if created_at is not None:
        persona_record.created_at = created_at
    db_session.add(persona_record)
    await db_session.flush()
    return persona_record


def build_find_user_persona_result(
    *,
    id: int = 1,
    identity: UUID | None = None,
    name: str = "Marta Quill",
    bio: str = "Writes about slow mornings and stronger coffee.",
    background: str | None = None,
    writing_style: str | None = None,
    sample_writing: str | None = None,
) -> FindUserPersonaResult:
    return FindUserPersonaResult(
        id=id,
        identity=identity or uuid4(),
        name=name,
        bio=bio,
        background=background,
        writing_style=writing_style,
        sample_writing=sample_writing,
    )


def _build_unique_name() -> str:
    return f"persona-{uuid4().hex}"
