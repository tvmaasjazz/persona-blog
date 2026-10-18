from datetime import UTC, datetime

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from libs.blog_posts.exceptions import BlogPostGenerateTextRunOutputInvalidException
from libs.blog_posts.inputs import CreateBlogPostFromGenerateTextRunInput
from libs.blog_posts.results import (
    BlogPostContentItemResult,
    BlogPostDetailResult,
    BlogPostPersonaResult,
    FindUserBlogPostListResult,
)
from libs.blog_posts.services import BlogPostService
from libs.content_items.services import ContentItemService
from libs.content_items.types import ContentType
from libs.core.exceptions import ForbiddenException, NotFoundException
from libs.database.orm import BlogPostOrm, ContentItemOrm, GenerateTextRunOrm
from libs.generate_text.services import GenerateTextRunService, GenerateTextStepService
from libs.generate_text.types import GenerateTextRunStatusType, GenerateTextStepStatusType
from libs.personas.services import PersonaService
from tests.factories.auth import build_auth_user
from tests.factories.blog_posts import (
    VALID_BLOG_POST_BODY,
    build_create_blog_post_input,
    build_update_blog_post_input,
    insert_blog_post_row,
)
from tests.factories.content_items import insert_content_item_row
from tests.factories.database import fetch_database_utc_now
from tests.factories.generate_text import (
    insert_generate_text_run_row,
    insert_generate_text_step_row,
)
from tests.factories.personas import insert_persona_row
from tests.factories.users import insert_user_row


def _build_blog_post_service(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> BlogPostService:
    return BlogPostService(
        db_session=db_session,
        content_item_service=ContentItemService(db_session=db_session),
        persona_service=PersonaService(db_session=db_session),
        generate_text_run_service=GenerateTextRunService(db_session_factory=db_session_factory),
        generate_text_step_service=GenerateTextStepService(db_session_factory=db_session_factory),
    )


async def _insert_blog_post(
    db_session: AsyncSession,
    *,
    created_by_id: int,
    persona_id: int,
    is_public: bool = False,
    published_at: datetime | None = None,
    title: str = "Why Slow Mornings Make Better Writers",
    created_at: datetime | None = None,
    deleted_at: datetime | None = None,
    deleted_by_id: int | None = None,
) -> tuple[ContentItemOrm, BlogPostOrm]:
    content_item_record = await insert_content_item_row(
        db_session,
        created_by_id=created_by_id,
        persona_id=persona_id,
        is_public=is_public,
        published_at=published_at,
        created_at=created_at,
        deleted_at=deleted_at,
        deleted_by_id=deleted_by_id,
    )
    blog_post_record = await insert_blog_post_row(
        db_session,
        created_by_id=created_by_id,
        content_item_id=content_item_record.id,
        title=title,
        deleted_at=deleted_at,
        deleted_by_id=deleted_by_id,
    )
    return content_item_record, blog_post_record


async def test_create_blog_post_persists_content_item_and_blog_post_rows(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(db_session, created_by_id=user_record.id)
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)
    create_blog_post_input = build_create_blog_post_input(
        persona_identity=persona_record.identity,
        title="A Persisted Post",
    )

    create_blog_post_result = await blog_post_service.create_blog_post(
        create_blog_post_input, auth_user
    )

    blog_post_query = select(BlogPostOrm).where(
        BlogPostOrm.identity == create_blog_post_result.identity
    )
    blog_post_record = await db_session.scalar(blog_post_query)
    assert blog_post_record is not None
    assert blog_post_record.title == "A Persisted Post"
    assert blog_post_record.created_by_id == auth_user.id
    content_item_query = select(ContentItemOrm).where(
        ContentItemOrm.id == blog_post_record.content_item_id
    )
    content_item_record = await db_session.scalar(content_item_query)
    assert content_item_record is not None
    assert content_item_record.persona_id == persona_record.id
    assert content_item_record.content_type == ContentType.BLOG_POST


async def test_create_blog_post_someone_elses_persona_raises_not_found_exception(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner_record = await insert_user_row(db_session)
    other_user_record = await insert_user_row(db_session)
    other_auth_user = build_auth_user(
        user_id=other_user_record.id, user_identity=other_user_record.identity
    )
    persona_record = await insert_persona_row(db_session, created_by_id=owner_record.id)
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)
    create_blog_post_input = build_create_blog_post_input(persona_identity=persona_record.identity)

    with pytest.raises(NotFoundException):
        await blog_post_service.create_blog_post(create_blog_post_input, other_auth_user)


async def test_create_blog_post_from_generate_text_run_persists_rows_and_links_run(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
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
    await insert_generate_text_step_row(
        db_session,
        run_id=generate_text_run_record.id,
        created_by_id=user_record.id,
        status=GenerateTextStepStatusType.SUCCEEDED,
        output_text=(
            "# My Great Title\n\n*A subtitle that explains more*\n\n" + VALID_BLOG_POST_BODY
        ),
    )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)
    create_blog_post_from_generate_text_run_input = CreateBlogPostFromGenerateTextRunInput(
        generate_text_run_identity=generate_text_run_record.identity,
        is_public=False,
        published_at=None,
    )

    create_blog_post_result = await blog_post_service.create_blog_post_from_generate_text_run(
        create_blog_post_from_generate_text_run_input, auth_user
    )

    blog_post_query = select(BlogPostOrm).where(
        BlogPostOrm.identity == create_blog_post_result.identity
    )
    blog_post_record = await db_session.scalar(blog_post_query)
    assert blog_post_record is not None
    assert blog_post_record.title == "My Great Title"
    assert blog_post_record.subtitle == "A subtitle that explains more"
    assert blog_post_record.body == VALID_BLOG_POST_BODY
    content_item_query = select(ContentItemOrm).where(
        ContentItemOrm.id == blog_post_record.content_item_id
    )
    content_item_record = await db_session.scalar(content_item_query)
    assert content_item_record is not None
    assert content_item_record.persona_id == persona_record.id
    assert content_item_record.content_type == ContentType.BLOG_POST
    updated_run_query = select(GenerateTextRunOrm).where(
        GenerateTextRunOrm.id == generate_text_run_record.id
    )
    updated_run_record = await db_session.scalar(updated_run_query)
    assert updated_run_record is not None
    assert updated_run_record.content_item_id == blog_post_record.content_item_id


async def test_create_blog_post_from_generate_text_run_no_subtitle_returns_none_subtitle(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
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
    await insert_generate_text_step_row(
        db_session,
        run_id=generate_text_run_record.id,
        created_by_id=user_record.id,
        status=GenerateTextStepStatusType.SUCCEEDED,
        output_text=f"# My Great Title\n\n{VALID_BLOG_POST_BODY}",
    )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)
    create_blog_post_from_generate_text_run_input = CreateBlogPostFromGenerateTextRunInput(
        generate_text_run_identity=generate_text_run_record.identity,
        is_public=False,
        published_at=None,
    )

    create_blog_post_result = await blog_post_service.create_blog_post_from_generate_text_run(
        create_blog_post_from_generate_text_run_input, auth_user
    )

    blog_post_query = select(BlogPostOrm).where(
        BlogPostOrm.identity == create_blog_post_result.identity
    )
    blog_post_record = await db_session.scalar(blog_post_query)
    assert blog_post_record is not None
    assert blog_post_record.title == "My Great Title"
    assert blog_post_record.subtitle is None
    assert blog_post_record.body == VALID_BLOG_POST_BODY


async def test_create_blog_post_from_generate_text_run_no_title_raises_invalid_exception(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
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
    await insert_generate_text_step_row(
        db_session,
        run_id=generate_text_run_record.id,
        created_by_id=user_record.id,
        status=GenerateTextStepStatusType.SUCCEEDED,
        output_text="Just a paragraph with no heading at all, so there is nothing to split.",
    )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)
    create_blog_post_from_generate_text_run_input = CreateBlogPostFromGenerateTextRunInput(
        generate_text_run_identity=generate_text_run_record.identity,
        is_public=False,
        published_at=None,
    )

    with pytest.raises(BlogPostGenerateTextRunOutputInvalidException):
        await blog_post_service.create_blog_post_from_generate_text_run(
            create_blog_post_from_generate_text_run_input, auth_user
        )


async def test_create_blog_post_from_generate_text_run_empty_body_raises_output_invalid_exception(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
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
    await insert_generate_text_step_row(
        db_session,
        run_id=generate_text_run_record.id,
        created_by_id=user_record.id,
        status=GenerateTextStepStatusType.SUCCEEDED,
        output_text="# Only A Title",
    )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)
    create_blog_post_from_generate_text_run_input = CreateBlogPostFromGenerateTextRunInput(
        generate_text_run_identity=generate_text_run_record.identity,
        is_public=False,
        published_at=None,
    )

    with pytest.raises(BlogPostGenerateTextRunOutputInvalidException):
        await blog_post_service.create_blog_post_from_generate_text_run(
            create_blog_post_from_generate_text_run_input, auth_user
        )


async def test_create_blog_post_from_generate_text_run_h4_in_body_raises_output_invalid_exception(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
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
    await insert_generate_text_step_row(
        db_session,
        run_id=generate_text_run_record.id,
        created_by_id=user_record.id,
        status=GenerateTextStepStatusType.SUCCEEDED,
        output_text=(
            "# My Great Title\n\n"
            "A paragraph that opens the post with some context.\n\n"
            "#### Too Deep Heading\n\n"
            "More text here."
        ),
    )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)
    create_blog_post_from_generate_text_run_input = CreateBlogPostFromGenerateTextRunInput(
        generate_text_run_identity=generate_text_run_record.identity,
        is_public=False,
        published_at=None,
    )

    with pytest.raises(BlogPostGenerateTextRunOutputInvalidException):
        await blog_post_service.create_blog_post_from_generate_text_run(
            create_blog_post_from_generate_text_run_input, auth_user
        )


async def test_create_blog_post_from_generate_text_run_no_persona_raises_output_invalid_exception(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    generate_text_run_record = await insert_generate_text_run_row(
        db_session,
        created_by_id=user_record.id,
        persona_id=None,
        status=GenerateTextRunStatusType.COMPLETED,
    )
    await insert_generate_text_step_row(
        db_session,
        run_id=generate_text_run_record.id,
        created_by_id=user_record.id,
        status=GenerateTextStepStatusType.SUCCEEDED,
        output_text=f"# My Great Title\n\n{VALID_BLOG_POST_BODY}",
    )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)
    create_blog_post_from_generate_text_run_input = CreateBlogPostFromGenerateTextRunInput(
        generate_text_run_identity=generate_text_run_record.identity,
        is_public=False,
        published_at=None,
    )

    with pytest.raises(BlogPostGenerateTextRunOutputInvalidException):
        await blog_post_service.create_blog_post_from_generate_text_run(
            create_blog_post_from_generate_text_run_input, auth_user
        )


async def test_find_blog_post_own_post_returns_blog_post_detail_result(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(db_session, created_by_id=user_record.id)
    _, blog_post_record = await _insert_blog_post(
        db_session, created_by_id=user_record.id, persona_id=persona_record.id
    )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    find_blog_post_result = await blog_post_service.find_blog_post(
        blog_post_record.identity, auth_user
    )

    assert find_blog_post_result == BlogPostDetailResult(
        identity=blog_post_record.identity,
        title=blog_post_record.title,
        subtitle=None,
        body=VALID_BLOG_POST_BODY,
        created_at=blog_post_record.created_at,
        updated_at=blog_post_record.updated_at,
        content_item=BlogPostContentItemResult(
            is_public=False,
            published_at=None,
            persona=BlogPostPersonaResult(identity=persona_record.identity),
        ),
    )


async def test_find_blog_post_others_published_post_returns_blog_post_detail_result(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner_record = await insert_user_row(db_session)
    other_user_record = await insert_user_row(db_session)
    other_auth_user = build_auth_user(
        user_id=other_user_record.id, user_identity=other_user_record.identity
    )
    persona_record = await insert_persona_row(
        db_session, created_by_id=owner_record.id, is_public=True
    )
    _, blog_post_record = await _insert_blog_post(
        db_session,
        created_by_id=owner_record.id,
        persona_id=persona_record.id,
        is_public=True,
        published_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    find_blog_post_result = await blog_post_service.find_blog_post(
        blog_post_record.identity, other_auth_user
    )

    assert find_blog_post_result == BlogPostDetailResult(
        identity=blog_post_record.identity,
        title=blog_post_record.title,
        subtitle=None,
        body=VALID_BLOG_POST_BODY,
        created_at=blog_post_record.created_at,
        updated_at=blog_post_record.updated_at,
        content_item=BlogPostContentItemResult(
            is_public=True,
            published_at=datetime(2020, 1, 1, tzinfo=UTC),
            persona=BlogPostPersonaResult(identity=persona_record.identity),
        ),
    )


async def test_find_blog_post_others_private_post_raises_not_found_exception(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner_record = await insert_user_row(db_session)
    other_user_record = await insert_user_row(db_session)
    other_auth_user = build_auth_user(
        user_id=other_user_record.id, user_identity=other_user_record.identity
    )
    persona_record = await insert_persona_row(db_session, created_by_id=owner_record.id)
    _, blog_post_record = await _insert_blog_post(
        db_session, created_by_id=owner_record.id, persona_id=persona_record.id
    )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    with pytest.raises(NotFoundException):
        await blog_post_service.find_blog_post(blog_post_record.identity, other_auth_user)


async def test_find_blog_post_deleted_raises_not_found_exception(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(db_session, created_by_id=user_record.id)
    deleted_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    _, blog_post_record = await _insert_blog_post(
        db_session,
        created_by_id=user_record.id,
        persona_id=persona_record.id,
        deleted_at=deleted_at,
        deleted_by_id=user_record.id,
    )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    with pytest.raises(NotFoundException):
        await blog_post_service.find_blog_post(blog_post_record.identity, auth_user)


async def test_find_user_blog_post_list_returns_only_own_newest_first(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    user_record = await insert_user_row(db_session)
    other_user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(db_session, created_by_id=user_record.id)
    other_persona_record = await insert_persona_row(
        db_session, created_by_id=other_user_record.id, is_public=True
    )
    _, oldest_blog_post_record = await _insert_blog_post(
        db_session,
        created_by_id=user_record.id,
        persona_id=persona_record.id,
        title="Oldest Post",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    _, newest_blog_post_record = await _insert_blog_post(
        db_session,
        created_by_id=user_record.id,
        persona_id=persona_record.id,
        title="Newest Post",
        created_at=datetime(2026, 1, 3, tzinfo=UTC),
    )
    await _insert_blog_post(
        db_session,
        created_by_id=user_record.id,
        persona_id=persona_record.id,
        title="Deleted Post",
        deleted_at=datetime(2026, 1, 4, tzinfo=UTC),
        deleted_by_id=user_record.id,
    )
    await _insert_blog_post(
        db_session,
        created_by_id=other_user_record.id,
        persona_id=other_persona_record.id,
        title="Other User's Post",
        is_public=True,
        published_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    find_user_blog_post_list_result = await blog_post_service.find_user_blog_post_list(
        auth_user, None
    )

    assert find_user_blog_post_list_result == FindUserBlogPostListResult(
        blog_posts=[
            BlogPostDetailResult(
                identity=newest_blog_post_record.identity,
                title="Newest Post",
                subtitle=None,
                body=VALID_BLOG_POST_BODY,
                created_at=newest_blog_post_record.created_at,
                updated_at=newest_blog_post_record.updated_at,
                content_item=BlogPostContentItemResult(
                    is_public=False,
                    published_at=None,
                    persona=BlogPostPersonaResult(identity=persona_record.identity),
                ),
            ),
            BlogPostDetailResult(
                identity=oldest_blog_post_record.identity,
                title="Oldest Post",
                subtitle=None,
                body=VALID_BLOG_POST_BODY,
                created_at=oldest_blog_post_record.created_at,
                updated_at=oldest_blog_post_record.updated_at,
                content_item=BlogPostContentItemResult(
                    is_public=False,
                    published_at=None,
                    persona=BlogPostPersonaResult(identity=persona_record.identity),
                ),
            ),
        ]
    )


async def test_find_user_blog_post_list_filters_by_persona_identity(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    matching_persona_record = await insert_persona_row(db_session, created_by_id=user_record.id)
    other_persona_record = await insert_persona_row(db_session, created_by_id=user_record.id)
    _, matching_blog_post_record = await _insert_blog_post(
        db_session,
        created_by_id=user_record.id,
        persona_id=matching_persona_record.id,
        title="Matching Post",
    )
    await _insert_blog_post(
        db_session,
        created_by_id=user_record.id,
        persona_id=other_persona_record.id,
        title="Other Persona's Post",
    )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    find_user_blog_post_list_result = await blog_post_service.find_user_blog_post_list(
        auth_user, matching_persona_record.identity
    )

    assert find_user_blog_post_list_result == FindUserBlogPostListResult(
        blog_posts=[
            BlogPostDetailResult(
                identity=matching_blog_post_record.identity,
                title="Matching Post",
                subtitle=None,
                body=VALID_BLOG_POST_BODY,
                created_at=matching_blog_post_record.created_at,
                updated_at=matching_blog_post_record.updated_at,
                content_item=BlogPostContentItemResult(
                    is_public=False,
                    published_at=None,
                    persona=BlogPostPersonaResult(identity=matching_persona_record.identity),
                ),
            )
        ]
    )


async def test_update_blog_post_own_post_updates_both_rows(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(
        db_session, created_by_id=user_record.id, is_public=True
    )
    _, blog_post_record = await _insert_blog_post(
        db_session, created_by_id=user_record.id, persona_id=persona_record.id, title="Old Title"
    )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)
    published_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    update_blog_post_input = build_update_blog_post_input(
        title="New Title", is_public=True, published_at=published_at
    )

    await blog_post_service.update_blog_post(
        blog_post_record.identity, update_blog_post_input, auth_user
    )

    blog_post_query = select(BlogPostOrm).where(BlogPostOrm.identity == blog_post_record.identity)
    updated_blog_post_record = await db_session.scalar(blog_post_query)
    assert updated_blog_post_record is not None
    assert updated_blog_post_record.title == "New Title"
    assert updated_blog_post_record.updated_by_id == auth_user.id
    content_item_query = select(ContentItemOrm).where(
        ContentItemOrm.id == updated_blog_post_record.content_item_id
    )
    updated_content_item_record = await db_session.scalar(content_item_query)
    assert updated_content_item_record is not None
    assert updated_content_item_record.is_public is True
    assert updated_content_item_record.published_at == published_at


async def test_update_blog_post_others_visible_post_raises_forbidden_exception(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner_record = await insert_user_row(db_session)
    other_user_record = await insert_user_row(db_session)
    other_auth_user = build_auth_user(
        user_id=other_user_record.id, user_identity=other_user_record.identity
    )
    persona_record = await insert_persona_row(
        db_session, created_by_id=owner_record.id, is_public=True
    )
    _, blog_post_record = await _insert_blog_post(
        db_session,
        created_by_id=owner_record.id,
        persona_id=persona_record.id,
        is_public=True,
        published_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    with pytest.raises(ForbiddenException):
        await blog_post_service.update_blog_post(
            blog_post_record.identity, build_update_blog_post_input(), other_auth_user
        )


async def test_update_blog_post_others_hidden_post_raises_not_found_exception(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner_record = await insert_user_row(db_session)
    other_user_record = await insert_user_row(db_session)
    other_auth_user = build_auth_user(
        user_id=other_user_record.id, user_identity=other_user_record.identity
    )
    persona_record = await insert_persona_row(db_session, created_by_id=owner_record.id)
    _, blog_post_record = await _insert_blog_post(
        db_session, created_by_id=owner_record.id, persona_id=persona_record.id
    )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    with pytest.raises(NotFoundException):
        await blog_post_service.update_blog_post(
            blog_post_record.identity, build_update_blog_post_input(), other_auth_user
        )


async def test_delete_blog_post_soft_deletes_both_rows(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(db_session, created_by_id=user_record.id)
    content_item_record, blog_post_record = await _insert_blog_post(
        db_session, created_by_id=user_record.id, persona_id=persona_record.id
    )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    await blog_post_service.delete_blog_post(blog_post_record.identity, auth_user)

    blog_post_orm_query = select(BlogPostOrm).where(
        BlogPostOrm.identity == blog_post_record.identity
    )
    blog_post_orm_result = await db_session.scalar(blog_post_orm_query)
    content_item_orm_query = select(ContentItemOrm).where(
        ContentItemOrm.id == content_item_record.id
    )
    content_item_orm_result = await db_session.scalar(content_item_orm_query)
    database_utc_now = await fetch_database_utc_now(db_session)
    raw_blog_post_query = text(
        "SELECT deleted_at, deleted_by_id FROM pb_blog_post WHERE identity = :identity"
    )
    raw_blog_post_result = (
        await db_session.execute(raw_blog_post_query, {"identity": str(blog_post_record.identity)})
    ).one()
    raw_content_item_query = text(
        "SELECT deleted_at, deleted_by_id FROM pb_content_item WHERE id = :content_item_id"
    )
    raw_content_item_result = (
        await db_session.execute(
            raw_content_item_query, {"content_item_id": content_item_record.id}
        )
    ).one()
    assert blog_post_orm_result is None
    assert content_item_orm_result is None
    assert raw_blog_post_result.deleted_at.replace(tzinfo=UTC) == database_utc_now
    assert raw_blog_post_result.deleted_by_id == auth_user.id
    assert raw_content_item_result.deleted_at.replace(tzinfo=UTC) == database_utc_now
    assert raw_content_item_result.deleted_by_id == auth_user.id
