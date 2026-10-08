from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from libs.content_items.exceptions import (
    ContentItemGenerateTextRunAlreadySavedException,
    ContentItemGenerateTextRunNotCompletedException,
    ContentItemPersonaPrivateException,
)
from libs.content_items.services import ContentItemValidationService
from libs.core.exceptions import NotFoundException
from libs.generate_text.types import GenerateTextRunStatusType
from tests.factories.auth import build_auth_user
from tests.factories.content_items import insert_content_item_row
from tests.factories.generate_text import insert_generate_text_run_row
from tests.factories.personas import insert_persona_row
from tests.factories.users import insert_user_row


async def test_validate_persona_allows_public_private_persona_raises_persona_private_exception(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(
        db_session, created_by_id=user_record.id, is_public=False
    )
    await db_session.commit()
    content_item_validation_service = ContentItemValidationService(db_session=db_session)

    with pytest.raises(ContentItemPersonaPrivateException):
        await content_item_validation_service.validate_persona_allows_public(
            persona_record.identity, True, auth_user
        )


async def test_validate_persona_allows_public_public_on_public_persona_returns_none(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(
        db_session, created_by_id=user_record.id, is_public=True
    )
    await db_session.commit()
    content_item_validation_service = ContentItemValidationService(db_session=db_session)

    validate_persona_allows_public_result = (
        await content_item_validation_service.validate_persona_allows_public(
            persona_record.identity, True, auth_user
        )
    )

    assert validate_persona_allows_public_result is None


async def test_validate_persona_allows_public_private_on_private_persona_returns_none(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(
        db_session, created_by_id=user_record.id, is_public=False
    )
    await db_session.commit()
    content_item_validation_service = ContentItemValidationService(db_session=db_session)

    validate_persona_allows_public_result = (
        await content_item_validation_service.validate_persona_allows_public(
            persona_record.identity, False, auth_user
        )
    )

    assert validate_persona_allows_public_result is None


async def test_validate_persona_allows_public_someone_elses_persona_returns_none(
    db_session: AsyncSession,
) -> None:
    owner_record = await insert_user_row(db_session)
    other_user_record = await insert_user_row(db_session)
    other_auth_user = build_auth_user(
        user_id=other_user_record.id, user_identity=other_user_record.identity
    )
    persona_record = await insert_persona_row(
        db_session, created_by_id=owner_record.id, is_public=False
    )
    await db_session.commit()
    content_item_validation_service = ContentItemValidationService(db_session=db_session)

    validate_persona_allows_public_result = (
        await content_item_validation_service.validate_persona_allows_public(
            persona_record.identity, True, other_auth_user
        )
    )

    assert validate_persona_allows_public_result is None


async def test_validate_persona_allows_public_missing_persona_returns_none(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    await db_session.commit()
    content_item_validation_service = ContentItemValidationService(db_session=db_session)

    validate_persona_allows_public_result = (
        await content_item_validation_service.validate_persona_allows_public(
            uuid4(), True, auth_user
        )
    )

    assert validate_persona_allows_public_result is None


async def test_validate_generate_text_run_available_missing_run_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    await db_session.commit()
    content_item_validation_service = ContentItemValidationService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await content_item_validation_service.validate_generate_text_run_available(
            uuid4(), auth_user
        )


async def test_validate_generate_text_run_available_another_users_run_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    owner_record = await insert_user_row(db_session)
    other_user_record = await insert_user_row(db_session)
    other_auth_user = build_auth_user(
        user_id=other_user_record.id, user_identity=other_user_record.identity
    )
    persona_record = await insert_persona_row(db_session, created_by_id=owner_record.id)
    generate_text_run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=owner_record.id,
        persona_id=persona_record.id,
        status=GenerateTextRunStatusType.COMPLETED,
    )
    await db_session.commit()
    content_item_validation_service = ContentItemValidationService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await content_item_validation_service.validate_generate_text_run_available(
            generate_text_run_record.identity, other_auth_user
        )


async def test_validate_generate_text_run_available_not_completed_raises_not_completed_exception(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(db_session, created_by_id=user_record.id)
    generate_text_run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=user_record.id,
        persona_id=persona_record.id,
        status=GenerateTextRunStatusType.RUNNING,
    )
    await db_session.commit()
    content_item_validation_service = ContentItemValidationService(db_session=db_session)

    with pytest.raises(ContentItemGenerateTextRunNotCompletedException):
        await content_item_validation_service.validate_generate_text_run_available(
            generate_text_run_record.identity, auth_user
        )


async def test_validate_generate_text_run_available_already_linked_raises_already_saved_exception(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(db_session, created_by_id=user_record.id)
    content_item_record = await insert_content_item_row(
        db_session, created_by_id=user_record.id, persona_id=persona_record.id
    )
    generate_text_run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=user_record.id,
        persona_id=persona_record.id,
        status=GenerateTextRunStatusType.COMPLETED,
        content_item_id=content_item_record.id,
    )
    await db_session.commit()
    content_item_validation_service = ContentItemValidationService(db_session=db_session)

    with pytest.raises(ContentItemGenerateTextRunAlreadySavedException):
        await content_item_validation_service.validate_generate_text_run_available(
            generate_text_run_record.identity, auth_user
        )


async def test_validate_generate_text_run_available_completed_unlinked_returns_none(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(db_session, created_by_id=user_record.id)
    generate_text_run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=user_record.id,
        persona_id=persona_record.id,
        status=GenerateTextRunStatusType.COMPLETED,
    )
    await db_session.commit()
    content_item_validation_service = ContentItemValidationService(db_session=db_session)

    validate_generate_text_run_available_result = (
        await content_item_validation_service.validate_generate_text_run_available(
            generate_text_run_record.identity, auth_user
        )
    )

    assert validate_generate_text_run_available_result is None


async def test_validate_generate_text_run_allows_public_private_persona_raises_private_exception(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(
        db_session, created_by_id=user_record.id, is_public=False
    )
    generate_text_run_record = await insert_generate_text_run_row(
        db_session, created_by_id=user_record.id, persona_id=persona_record.id
    )
    await db_session.commit()
    content_item_validation_service = ContentItemValidationService(db_session=db_session)

    with pytest.raises(ContentItemPersonaPrivateException):
        await content_item_validation_service.validate_generate_text_run_allows_public(
            generate_text_run_record.identity, True, auth_user
        )


async def test_validate_generate_text_run_allows_public_public_persona_returns_none(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(
        db_session, created_by_id=user_record.id, is_public=True
    )
    generate_text_run_record = await insert_generate_text_run_row(
        db_session, created_by_id=user_record.id, persona_id=persona_record.id
    )
    await db_session.commit()
    content_item_validation_service = ContentItemValidationService(db_session=db_session)

    validate_generate_text_run_allows_public_result = (
        await content_item_validation_service.validate_generate_text_run_allows_public(
            generate_text_run_record.identity, True, auth_user
        )
    )

    assert validate_generate_text_run_allows_public_result is None


async def test_validate_generate_text_run_allows_public_private_persona_not_public_returns_none(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(
        db_session, created_by_id=user_record.id, is_public=False
    )
    generate_text_run_record = await insert_generate_text_run_row(
        db_session, created_by_id=user_record.id, persona_id=persona_record.id
    )
    await db_session.commit()
    content_item_validation_service = ContentItemValidationService(db_session=db_session)

    validate_generate_text_run_allows_public_result = (
        await content_item_validation_service.validate_generate_text_run_allows_public(
            generate_text_run_record.identity, False, auth_user
        )
    )

    assert validate_generate_text_run_allows_public_result is None


async def test_validate_generate_text_run_allows_public_another_users_run_returns_none(
    db_session: AsyncSession,
) -> None:
    owner_record = await insert_user_row(db_session)
    other_user_record = await insert_user_row(db_session)
    other_auth_user = build_auth_user(
        user_id=other_user_record.id, user_identity=other_user_record.identity
    )
    persona_record = await insert_persona_row(
        db_session, created_by_id=owner_record.id, is_public=False
    )
    generate_text_run_record = await insert_generate_text_run_row(
        db_session, created_by_id=owner_record.id, persona_id=persona_record.id
    )
    await db_session.commit()
    content_item_validation_service = ContentItemValidationService(db_session=db_session)

    validate_generate_text_run_allows_public_result = (
        await content_item_validation_service.validate_generate_text_run_allows_public(
            generate_text_run_record.identity, True, other_auth_user
        )
    )

    assert validate_generate_text_run_allows_public_result is None


async def test_validate_generate_text_run_allows_public_unknown_run_returns_none(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    await db_session.commit()
    content_item_validation_service = ContentItemValidationService(db_session=db_session)

    validate_generate_text_run_allows_public_result = (
        await content_item_validation_service.validate_generate_text_run_allows_public(
            uuid4(), True, auth_user
        )
    )

    assert validate_generate_text_run_allows_public_result is None


async def test_validate_generate_text_run_allows_public_run_with_no_persona_returns_none(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    generate_text_run_record = await insert_generate_text_run_row(
        db_session, created_by_id=user_record.id, persona_id=None
    )
    await db_session.commit()
    content_item_validation_service = ContentItemValidationService(db_session=db_session)

    validate_generate_text_run_allows_public_result = (
        await content_item_validation_service.validate_generate_text_run_allows_public(
            generate_text_run_record.identity, True, auth_user
        )
    )

    assert validate_generate_text_run_allows_public_result is None
