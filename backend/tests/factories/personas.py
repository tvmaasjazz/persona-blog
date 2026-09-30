from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from libs.database.orm import PersonaOrm
from libs.personas.inputs import PersonaInput
from libs.personas.results import FindUserPersonaResult


def build_persona_input(
    *,
    name: str | None = None,
    bio: str = "Writes about coffee and slow mornings.",
    avatar_url: str | None = None,
    background: str | None = None,
    expertise: str | None = None,
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
        expertise=expertise,
        writing_style=writing_style,
        default_tone=default_tone,
        default_target_audience=default_target_audience,
        sample_writing=sample_writing,
        is_public=is_public,
    )


async def insert_persona_row(
    db_session: AsyncSession,
    *,
    created_by_id: int,
    name: str | None = None,
    bio: str = "Writes about coffee and slow mornings.",
    avatar_url: str | None = None,
    background: str | None = None,
    expertise: str | None = None,
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
        expertise=expertise,
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
    expertise: str | None = None,
    writing_style: str | None = None,
    sample_writing: str | None = None,
) -> FindUserPersonaResult:
    return FindUserPersonaResult(
        id=id,
        identity=identity or uuid4(),
        name=name,
        bio=bio,
        background=background,
        expertise=expertise,
        writing_style=writing_style,
        sample_writing=sample_writing,
    )


def _build_unique_name() -> str:
    return f"persona-{uuid4().hex}"
