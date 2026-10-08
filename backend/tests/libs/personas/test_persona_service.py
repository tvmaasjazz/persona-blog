from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from libs.auth.results import AuthUser
from libs.core.exceptions import ForbiddenException, NotFoundException
from libs.database.orm import PersonaOrm
from libs.personas.results import (
    CreatePersonaResult,
    FindUserPersonaListResult,
    FindUserPersonaResult,
    PersonaDetailResult,
)
from libs.personas.services import PersonaService
from tests.factories.auth import build_auth_user
from tests.factories.personas import build_persona_input, insert_persona_row
from tests.factories.users import insert_user_row


async def _insert_auth_user(db_session: AsyncSession) -> AuthUser:
    user_record = await insert_user_row(db_session)
    await db_session.commit()
    return build_auth_user(user_id=user_record.id, user_identity=user_record.identity)


async def test_create_persona_persists_row(db_session: AsyncSession) -> None:
    auth_user = await _insert_auth_user(db_session)
    persona_service = PersonaService(db_session=db_session)
    persona_input = build_persona_input(
        name="Ada the Essayist",
        bio="Writes long-form essays on computing history.",
        avatar_url="https://example.com/ada.png",
        background="Former mathematician.",
        writing_style="Formal",
        default_tone="Warm",
        default_target_audience="Engineers",
        sample_writing="It was a cold morning in London.",
    )

    create_persona_result = await persona_service.create_persona(persona_input, auth_user)

    persona_query = select(PersonaOrm).where(PersonaOrm.identity == create_persona_result.identity)
    persona_record = await db_session.scalar(persona_query)
    assert create_persona_result == CreatePersonaResult(identity=persona_record.identity)
    assert persona_record is not None
    assert persona_record.name == "Ada the Essayist"
    assert persona_record.bio == "Writes long-form essays on computing history."
    assert persona_record.avatar_url == "https://example.com/ada.png"
    assert persona_record.background == "Former mathematician."
    assert persona_record.writing_style == "Formal"
    assert persona_record.default_tone == "Warm"
    assert persona_record.default_target_audience == "Engineers"
    assert persona_record.sample_writing == "It was a cold morning in London."
    assert persona_record.created_by_id == auth_user.id
    assert persona_record.updated_by_id == auth_user.id
    assert persona_record.created_at is not None
    assert persona_record.is_public is False


@pytest.mark.parametrize(
    ("is_public", "expected_is_public"),
    [
        pytest.param(True, True, id="public"),
        pytest.param(False, False, id="private"),
    ],
)
async def test_create_persona_persists_is_public(
    db_session: AsyncSession, is_public: bool, expected_is_public: bool
) -> None:
    auth_user = await _insert_auth_user(db_session)
    persona_service = PersonaService(db_session=db_session)
    persona_input = build_persona_input(is_public=is_public)

    create_persona_result = await persona_service.create_persona(persona_input, auth_user)

    persona_query = select(PersonaOrm).where(PersonaOrm.identity == create_persona_result.identity)
    persona_record = await db_session.scalar(persona_query)
    assert persona_record is not None
    assert persona_record.is_public is expected_is_public


async def test_create_persona_same_name_different_user_persists_row(
    db_session: AsyncSession,
) -> None:
    first_auth_user = await _insert_auth_user(db_session)
    second_auth_user = await _insert_auth_user(db_session)
    persona_service = PersonaService(db_session=db_session)
    await persona_service.create_persona(
        build_persona_input(name="Ada the Essayist"), first_auth_user
    )

    create_persona_result = await persona_service.create_persona(
        build_persona_input(name="Ada the Essayist"), second_auth_user
    )

    persona_query = select(PersonaOrm).where(PersonaOrm.identity == create_persona_result.identity)
    persona_record = await db_session.scalar(persona_query)
    assert persona_record is not None
    assert persona_record.created_by_id == second_auth_user.id


async def test_create_persona_same_name_after_soft_delete_persists_row(
    db_session: AsyncSession,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    persona_service = PersonaService(db_session=db_session)
    first_create_result = await persona_service.create_persona(
        build_persona_input(name="Ada the Essayist"), auth_user
    )
    await persona_service.delete_persona(first_create_result.identity, auth_user)

    create_persona_result = await persona_service.create_persona(
        build_persona_input(name="Ada the Essayist"), auth_user
    )

    persona_query = select(PersonaOrm).where(PersonaOrm.identity == create_persona_result.identity)
    persona_record = await db_session.scalar(persona_query)
    assert persona_record is not None
    assert persona_record.deleted_at is None


async def test_find_persona_returns_persona_detail_result(db_session: AsyncSession) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(
        db_session,
        created_by_id=user_record.id,
        name="Ada the Essayist",
        bio="Writes long-form essays.",
    )
    persona_service = PersonaService(db_session=db_session)

    find_persona_result = await persona_service.find_persona(persona_record.identity, auth_user)

    assert find_persona_result == PersonaDetailResult(
        identity=persona_record.identity,
        name="Ada the Essayist",
        bio="Writes long-form essays.",
        avatar_url=None,
        background=None,
        writing_style=None,
        default_tone=None,
        default_target_audience=None,
        sample_writing=None,
        is_public=False,
        created_at=persona_record.created_at,
        updated_at=persona_record.updated_at,
    )


async def test_find_persona_never_inserted_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    persona_service = PersonaService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await persona_service.find_persona(uuid4(), auth_user)


async def test_find_persona_soft_deleted_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    deleted_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    persona_record = await insert_persona_row(
        db_session,
        created_by_id=user_record.id,
        deleted_at=deleted_at,
        deleted_by_id=user_record.id,
    )
    persona_service = PersonaService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await persona_service.find_persona(persona_record.identity, auth_user)


async def test_find_persona_another_users_private_persona_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    owner_record = await insert_user_row(db_session)
    other_user_record = await insert_user_row(db_session)
    other_auth_user = build_auth_user(
        user_id=other_user_record.id, user_identity=other_user_record.identity
    )
    persona_record = await insert_persona_row(db_session, created_by_id=owner_record.id)
    persona_service = PersonaService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await persona_service.find_persona(persona_record.identity, other_auth_user)


async def test_find_persona_another_users_public_persona_returns_persona_detail_result(
    db_session: AsyncSession,
) -> None:
    owner_record = await insert_user_row(db_session)
    other_user_record = await insert_user_row(db_session)
    other_auth_user = build_auth_user(
        user_id=other_user_record.id, user_identity=other_user_record.identity
    )
    persona_record = await insert_persona_row(
        db_session,
        created_by_id=owner_record.id,
        name="Ada the Essayist",
        bio="Writes long-form essays.",
        is_public=True,
    )
    persona_service = PersonaService(db_session=db_session)

    find_persona_result = await persona_service.find_persona(
        persona_record.identity, other_auth_user
    )

    assert find_persona_result == PersonaDetailResult(
        identity=persona_record.identity,
        name="Ada the Essayist",
        bio="Writes long-form essays.",
        avatar_url=None,
        background=None,
        writing_style=None,
        default_tone=None,
        default_target_audience=None,
        sample_writing=None,
        is_public=True,
        created_at=persona_record.created_at,
        updated_at=persona_record.updated_at,
    )


async def test_find_user_persona_list_returns_only_live_personas_newest_first(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    other_user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    oldest_persona_record = await insert_persona_row(
        db_session,
        created_by_id=user_record.id,
        name="Oldest Persona",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    newest_persona_record = await insert_persona_row(
        db_session,
        created_by_id=user_record.id,
        name="Newest Persona",
        created_at=datetime(2026, 1, 3, tzinfo=UTC),
    )
    middle_persona_record = await insert_persona_row(
        db_session,
        created_by_id=user_record.id,
        name="Middle Persona",
        created_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    await insert_persona_row(
        db_session,
        created_by_id=user_record.id,
        name="Deleted Persona",
        deleted_at=datetime(2026, 1, 4, tzinfo=UTC),
        deleted_by_id=user_record.id,
    )
    await insert_persona_row(db_session, created_by_id=other_user_record.id, name="Other Persona")
    await insert_persona_row(
        db_session, created_by_id=other_user_record.id, name="Other Public Persona", is_public=True
    )
    persona_service = PersonaService(db_session=db_session)

    find_user_persona_list_result = await persona_service.find_user_persona_list(auth_user)

    assert find_user_persona_list_result == FindUserPersonaListResult(
        personas=[
            PersonaDetailResult.model_validate(newest_persona_record, from_attributes=True),
            PersonaDetailResult.model_validate(middle_persona_record, from_attributes=True),
            PersonaDetailResult.model_validate(oldest_persona_record, from_attributes=True),
        ]
    )


async def test_find_user_persona_list_no_personas_returns_empty_list(
    db_session: AsyncSession,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    persona_service = PersonaService(db_session=db_session)

    find_user_persona_list_result = await persona_service.find_user_persona_list(auth_user)

    assert find_user_persona_list_result == FindUserPersonaListResult(personas=[])


async def test_find_user_persona_own_persona_returns_result_with_id(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(
        db_session,
        created_by_id=user_record.id,
        name="Ada the Essayist",
        bio="Writes long-form essays.",
    )
    persona_service = PersonaService(db_session=db_session)

    find_user_persona_result = await persona_service.find_user_persona(
        persona_record.identity, auth_user
    )

    assert find_user_persona_result == FindUserPersonaResult(
        id=persona_record.id,
        identity=persona_record.identity,
        name="Ada the Essayist",
        bio="Writes long-form essays.",
        background=None,
        writing_style=None,
        sample_writing=None,
    )


async def test_find_user_persona_another_users_public_persona_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    owner_record = await insert_user_row(db_session)
    other_user_record = await insert_user_row(db_session)
    other_auth_user = build_auth_user(
        user_id=other_user_record.id, user_identity=other_user_record.identity
    )
    persona_record = await insert_persona_row(
        db_session, created_by_id=owner_record.id, is_public=True
    )
    persona_service = PersonaService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await persona_service.find_user_persona(persona_record.identity, other_auth_user)


async def test_find_user_persona_another_users_private_persona_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    owner_record = await insert_user_row(db_session)
    other_user_record = await insert_user_row(db_session)
    other_auth_user = build_auth_user(
        user_id=other_user_record.id, user_identity=other_user_record.identity
    )
    persona_record = await insert_persona_row(db_session, created_by_id=owner_record.id)
    persona_service = PersonaService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await persona_service.find_user_persona(persona_record.identity, other_auth_user)


async def test_find_user_persona_soft_deleted_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    deleted_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    persona_record = await insert_persona_row(
        db_session,
        created_by_id=user_record.id,
        deleted_at=deleted_at,
        deleted_by_id=user_record.id,
    )
    persona_service = PersonaService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await persona_service.find_user_persona(persona_record.identity, auth_user)


async def test_find_user_persona_never_inserted_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    persona_service = PersonaService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await persona_service.find_user_persona(uuid4(), auth_user)


async def test_update_persona_replaces_fields(db_session: AsyncSession) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(
        db_session,
        created_by_id=user_record.id,
        name="Old Name",
        bio="Old bio.",
        background="Old background.",
        is_public=True,
    )
    await db_session.commit()
    persona_service = PersonaService(db_session=db_session)
    updated_persona_input = build_persona_input(name="New Name", bio="New bio.")

    await persona_service.update_persona(persona_record.identity, updated_persona_input, auth_user)

    persona_query = select(PersonaOrm).where(PersonaOrm.identity == persona_record.identity)
    updated_persona_record = await db_session.scalar(persona_query)
    assert updated_persona_record is not None
    assert updated_persona_record.name == "New Name"
    assert updated_persona_record.bio == "New bio."
    assert updated_persona_record.background is None
    assert updated_persona_record.is_public is False
    assert updated_persona_record.updated_by_id == auth_user.id
    assert updated_persona_record.created_by_id == user_record.id


async def test_update_persona_never_inserted_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    persona_service = PersonaService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await persona_service.update_persona(uuid4(), build_persona_input(), auth_user)


async def test_update_persona_another_users_private_persona_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    owner_record = await insert_user_row(db_session)
    other_user_record = await insert_user_row(db_session)
    other_auth_user = build_auth_user(
        user_id=other_user_record.id, user_identity=other_user_record.identity
    )
    persona_record = await insert_persona_row(db_session, created_by_id=owner_record.id)
    await db_session.commit()
    persona_service = PersonaService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await persona_service.update_persona(
            persona_record.identity, build_persona_input(), other_auth_user
        )


async def test_update_persona_another_users_public_persona_raises_forbidden_exception(
    db_session: AsyncSession,
) -> None:
    owner_record = await insert_user_row(db_session)
    other_user_record = await insert_user_row(db_session)
    other_auth_user = build_auth_user(
        user_id=other_user_record.id, user_identity=other_user_record.identity
    )
    persona_record = await insert_persona_row(
        db_session, created_by_id=owner_record.id, is_public=True
    )
    await db_session.commit()
    persona_service = PersonaService(db_session=db_session)

    with pytest.raises(ForbiddenException):
        await persona_service.update_persona(
            persona_record.identity, build_persona_input(), other_auth_user
        )


async def test_delete_persona_soft_deletes_row(db_session: AsyncSession) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(db_session, created_by_id=user_record.id)
    await db_session.commit()
    persona_service = PersonaService(db_session=db_session)

    await persona_service.delete_persona(persona_record.identity, auth_user)

    orm_query = select(PersonaOrm).where(PersonaOrm.identity == persona_record.identity)
    orm_result = await db_session.scalar(orm_query)
    raw_query = text("SELECT deleted_at, deleted_by_id FROM pb_persona WHERE identity = :identity")
    raw_result = (
        await db_session.execute(raw_query, {"identity": str(persona_record.identity)})
    ).one()
    assert orm_result is None
    assert raw_result.deleted_at is not None
    assert raw_result.deleted_by_id == auth_user.id


async def test_delete_persona_never_inserted_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    auth_user = await _insert_auth_user(db_session)
    persona_service = PersonaService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await persona_service.delete_persona(uuid4(), auth_user)


async def test_delete_persona_another_users_private_persona_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    owner_record = await insert_user_row(db_session)
    other_user_record = await insert_user_row(db_session)
    other_auth_user = build_auth_user(
        user_id=other_user_record.id, user_identity=other_user_record.identity
    )
    persona_record = await insert_persona_row(db_session, created_by_id=owner_record.id)
    await db_session.commit()
    persona_service = PersonaService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await persona_service.delete_persona(persona_record.identity, other_auth_user)


async def test_delete_persona_another_users_public_persona_raises_forbidden_exception(
    db_session: AsyncSession,
) -> None:
    owner_record = await insert_user_row(db_session)
    other_user_record = await insert_user_row(db_session)
    other_auth_user = build_auth_user(
        user_id=other_user_record.id, user_identity=other_user_record.identity
    )
    persona_record = await insert_persona_row(
        db_session, created_by_id=owner_record.id, is_public=True
    )
    await db_session.commit()
    persona_service = PersonaService(db_session=db_session)

    with pytest.raises(ForbiddenException):
        await persona_service.delete_persona(persona_record.identity, other_auth_user)
