from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from libs.blog_posts.exceptions import BlogPostBodyInvalidException
from libs.blog_posts.services import BlogPostValidationService
from libs.content_items.exceptions import ContentItemPersonaPrivateException
from libs.content_items.services import ContentItemValidationService
from tests.factories.auth import build_auth_user
from tests.factories.blog_posts import insert_blog_post_row
from tests.factories.content_items import insert_content_item_row
from tests.factories.personas import insert_persona_row
from tests.factories.users import insert_user_row


def _build_blog_post_validation_service() -> BlogPostValidationService:
    return BlogPostValidationService(db_session=None, content_item_validation_service=None)


def test_validate_blog_post_body_paragraph_then_h2_h3_h2_passes() -> None:
    body = (
        "A paragraph that opens the post.\n\n## A Section\n\n### A Subsection\n\n## Another Section"
    )
    blog_post_validation_service = _build_blog_post_validation_service()

    blog_post_validation_service.validate_blog_post_body(body)


def test_validate_blog_post_body_opening_at_h3_raises_blog_post_body_invalid_exception() -> None:
    body = "### Opens Too Deep\n\nA paragraph."
    blog_post_validation_service = _build_blog_post_validation_service()

    with pytest.raises(BlogPostBodyInvalidException):
        blog_post_validation_service.validate_blog_post_body(body)


def test_validate_blog_post_body_h4_raises_blog_post_body_invalid_exception() -> None:
    body = "## A Section\n\n#### Too Deep"
    blog_post_validation_service = _build_blog_post_validation_service()

    with pytest.raises(BlogPostBodyInvalidException):
        blog_post_validation_service.validate_blog_post_body(body)


def test_validate_blog_post_body_h1_raises_blog_post_body_invalid_exception() -> None:
    body = "# Not Allowed Here\n\nA paragraph."
    blog_post_validation_service = _build_blog_post_validation_service()

    with pytest.raises(BlogPostBodyInvalidException):
        blog_post_validation_service.validate_blog_post_body(body)


def test_validate_blog_post_body_raw_html_block_raises_blog_post_body_invalid_exception() -> None:
    body = "<div>Hello</div>\n\n## A Section"
    blog_post_validation_service = _build_blog_post_validation_service()

    with pytest.raises(BlogPostBodyInvalidException):
        blog_post_validation_service.validate_blog_post_body(body)


def test_validate_blog_post_body_raw_html_inline_raises_blog_post_body_invalid_exception() -> None:
    body = "## A Section\n\nSome text with <span>inline</span> html."
    blog_post_validation_service = _build_blog_post_validation_service()

    with pytest.raises(BlogPostBodyInvalidException):
        blog_post_validation_service.validate_blog_post_body(body)


def test_validate_blog_post_body_image_raises_blog_post_body_invalid_exception() -> None:
    body = "## A Section\n\n![alt](http://example.com/photo.png)"
    blog_post_validation_service = _build_blog_post_validation_service()

    with pytest.raises(BlogPostBodyInvalidException):
        blog_post_validation_service.validate_blog_post_body(body)


def test_validate_blog_post_body_multiple_problems_lists_them_together() -> None:
    body = "# Not Allowed\n\n<div>Hello</div>\n\n![alt](http://example.com/a.png)"
    blog_post_validation_service = _build_blog_post_validation_service()

    with pytest.raises(BlogPostBodyInvalidException) as exception_info:
        blog_post_validation_service.validate_blog_post_body(body)

    exception_message = str(exception_info.value)
    assert "H1 heading" in exception_message
    assert "H2 and H3" in exception_message
    assert "raw HTML" in exception_message
    assert "images" in exception_message


def _build_db_backed_blog_post_validation_service(
    db_session: AsyncSession,
) -> BlogPostValidationService:
    return BlogPostValidationService(
        db_session=db_session,
        content_item_validation_service=ContentItemValidationService(db_session=db_session),
    )


async def test_validate_blog_post_visibility_private_persona_raises_persona_private_exception(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(
        db_session, created_by_id=user_record.id, is_public=False
    )
    content_item_record = await insert_content_item_row(
        db_session, created_by_id=user_record.id, persona_id=persona_record.id
    )
    blog_post_record = await insert_blog_post_row(
        db_session, created_by_id=user_record.id, content_item_id=content_item_record.id
    )
    await db_session.commit()
    blog_post_validation_service = _build_db_backed_blog_post_validation_service(db_session)

    with pytest.raises(ContentItemPersonaPrivateException):
        await blog_post_validation_service.validate_blog_post_visibility(
            blog_post_record.identity, True, auth_user
        )


async def test_validate_blog_post_visibility_public_on_public_persona_returns_none(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(
        db_session, created_by_id=user_record.id, is_public=True
    )
    content_item_record = await insert_content_item_row(
        db_session, created_by_id=user_record.id, persona_id=persona_record.id
    )
    blog_post_record = await insert_blog_post_row(
        db_session, created_by_id=user_record.id, content_item_id=content_item_record.id
    )
    await db_session.commit()
    blog_post_validation_service = _build_db_backed_blog_post_validation_service(db_session)

    validate_blog_post_visibility_result = (
        await blog_post_validation_service.validate_blog_post_visibility(
            blog_post_record.identity, True, auth_user
        )
    )

    assert validate_blog_post_visibility_result is None


async def test_validate_blog_post_visibility_private_on_private_persona_returns_none(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(
        db_session, created_by_id=user_record.id, is_public=False
    )
    content_item_record = await insert_content_item_row(
        db_session, created_by_id=user_record.id, persona_id=persona_record.id
    )
    blog_post_record = await insert_blog_post_row(
        db_session, created_by_id=user_record.id, content_item_id=content_item_record.id
    )
    await db_session.commit()
    blog_post_validation_service = _build_db_backed_blog_post_validation_service(db_session)

    validate_blog_post_visibility_result = (
        await blog_post_validation_service.validate_blog_post_visibility(
            blog_post_record.identity, False, auth_user
        )
    )

    assert validate_blog_post_visibility_result is None


async def test_validate_blog_post_visibility_someone_elses_post_returns_none(
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
    content_item_record = await insert_content_item_row(
        db_session, created_by_id=owner_record.id, persona_id=persona_record.id
    )
    blog_post_record = await insert_blog_post_row(
        db_session, created_by_id=owner_record.id, content_item_id=content_item_record.id
    )
    await db_session.commit()
    blog_post_validation_service = _build_db_backed_blog_post_validation_service(db_session)

    validate_blog_post_visibility_result = (
        await blog_post_validation_service.validate_blog_post_visibility(
            blog_post_record.identity, True, other_auth_user
        )
    )

    assert validate_blog_post_visibility_result is None


async def test_validate_blog_post_visibility_missing_blog_post_returns_none(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    await db_session.commit()
    blog_post_validation_service = _build_db_backed_blog_post_validation_service(db_session)

    validate_blog_post_visibility_result = (
        await blog_post_validation_service.validate_blog_post_visibility(uuid4(), True, auth_user)
    )

    assert validate_blog_post_visibility_result is None
