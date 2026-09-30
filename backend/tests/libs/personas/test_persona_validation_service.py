from datetime import UTC, datetime

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from libs.personas.exceptions import PersonaNameTakenException
from libs.personas.services import PersonaValidationService
from tests.factories.auth import build_auth_user
from tests.factories.personas import insert_persona_row
from tests.factories.users import insert_user_row


async def test_validate_persona_name_available_taken_name_raises_persona_name_taken_exception(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    await insert_persona_row(db_session, created_by_id=user_record.id, name="Ada the Essayist")
    await db_session.commit()
    persona_validation_service = PersonaValidationService(db_session=db_session)

    with pytest.raises(PersonaNameTakenException):
        await persona_validation_service.validate_persona_name_available(
            "Ada the Essayist", auth_user
        )


async def test_validate_persona_name_available_free_name_returns_none(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    await db_session.commit()
    persona_validation_service = PersonaValidationService(db_session=db_session)

    validate_persona_name_available_result = (
        await persona_validation_service.validate_persona_name_available(
            "Ada the Essayist", auth_user
        )
    )

    assert validate_persona_name_available_result is None


async def test_validate_persona_name_available_same_name_different_user_returns_none(
    db_session: AsyncSession,
) -> None:
    owner_record = await insert_user_row(db_session)
    other_user_record = await insert_user_row(db_session)
    other_auth_user = build_auth_user(
        user_id=other_user_record.id, user_identity=other_user_record.identity
    )
    await insert_persona_row(db_session, created_by_id=owner_record.id, name="Ada the Essayist")
    await db_session.commit()
    persona_validation_service = PersonaValidationService(db_session=db_session)

    validate_persona_name_available_result = (
        await persona_validation_service.validate_persona_name_available(
            "Ada the Essayist", other_auth_user
        )
    )

    assert validate_persona_name_available_result is None


async def test_validate_persona_name_available_same_name_soft_deleted_persona_returns_none(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    await insert_persona_row(
        db_session,
        created_by_id=user_record.id,
        name="Ada the Essayist",
        deleted_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        deleted_by_id=user_record.id,
    )
    await db_session.commit()
    persona_validation_service = PersonaValidationService(db_session=db_session)

    validate_persona_name_available_result = (
        await persona_validation_service.validate_persona_name_available(
            "Ada the Essayist", auth_user
        )
    )

    assert validate_persona_name_available_result is None


async def test_validate_persona_name_available_persona_identity_owns_name_returns_none(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(
        db_session, created_by_id=user_record.id, name="Ada the Essayist"
    )
    await db_session.commit()
    persona_validation_service = PersonaValidationService(db_session=db_session)

    validate_persona_name_available_result = (
        await persona_validation_service.validate_persona_name_available(
            "Ada the Essayist", auth_user, persona_record.identity
        )
    )

    assert validate_persona_name_available_result is None


async def test_validate_persona_name_available_taken_by_other_raises_persona_name_taken_exception(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    await insert_persona_row(db_session, created_by_id=user_record.id, name="Ada the Essayist")
    other_persona_record = await insert_persona_row(
        db_session, created_by_id=user_record.id, name="Second Persona"
    )
    await db_session.commit()
    persona_validation_service = PersonaValidationService(db_session=db_session)

    with pytest.raises(PersonaNameTakenException):
        await persona_validation_service.validate_persona_name_available(
            "Ada the Essayist", auth_user, other_persona_record.identity
        )
