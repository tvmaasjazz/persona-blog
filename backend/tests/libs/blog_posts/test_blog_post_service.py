from datetime import UTC, datetime
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from libs.blog_posts.exceptions import BlogPostGenerateTextRunOutputInvalidException
from libs.blog_posts.inputs import CreateBlogPostFromGenerateTextRunInput
from libs.blog_posts.results import (
    BlogPostContentItemResult,
    BlogPostDetailResult,
    BlogPostPersonaResult,
    BlogPostSummaryResult,
    FindPublicBlogPostListResult,
    FindUserBlogPostListResult,
    PublicBlogPostResult,
)
from libs.blog_posts.services import BlogPostService
from libs.blog_posts.types import PublicBlogPostSortType
from libs.content_items.services import ContentItemService
from libs.content_items.types import ContentType
from libs.core.exceptions import ForbiddenException, NotFoundException
from libs.core.results import PageInfoResult
from libs.core.types import SortDirectionType
from libs.database.orm import BlogPostOrm, ContentItemOrm, GenerateTextRunOrm
from libs.database.services import PageQueryService
from libs.generate_text.services import GenerateTextRunService, GenerateTextStepService
from libs.generate_text.types import GenerateTextRunStatusType, GenerateTextStepStatusType
from libs.personas.services import PersonaService
from tests.factories.auth import build_auth_user
from tests.factories.blog_posts import (
    VALID_BLOG_POST_BODY,
    build_create_blog_post_input,
    build_find_public_blog_post_list_input,
    build_update_blog_post_input,
    insert_blog_post_row,
)
from tests.factories.content_items import insert_content_item_row
from tests.factories.credits import build_credit_settings
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
        generate_text_step_service=GenerateTextStepService(
            db_session_factory=db_session_factory, credit_settings=build_credit_settings()
        ),
        page_query_service=PageQueryService(db_session=db_session),
    )


async def _insert_blog_post(
    db_session: AsyncSession,
    *,
    created_by_id: int,
    persona_id: int,
    is_public: bool = False,
    published_at: datetime | None = None,
    title: str = "Why Slow Mornings Make Better Writers",
    subtitle: str | None = None,
    body: str = VALID_BLOG_POST_BODY,
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
        subtitle=subtitle,
        body=body,
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


async def test_find_blog_post_others_published_post_raises_not_found_exception(
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

    with pytest.raises(NotFoundException):
        await blog_post_service.find_blog_post(blog_post_record.identity, other_auth_user)


async def test_find_public_blog_post_signed_out_published_post_returns_result_not_owner(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner_record = await insert_user_row(db_session)
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

    find_public_blog_post_result = await blog_post_service.find_public_blog_post(
        blog_post_record.identity, None
    )

    assert find_public_blog_post_result == PublicBlogPostResult(
        blog_post=BlogPostDetailResult(
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
        ),
        is_owner=False,
    )


async def test_find_public_blog_post_another_users_published_post_returns_result_not_owner(
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

    find_public_blog_post_result = await blog_post_service.find_public_blog_post(
        blog_post_record.identity, other_auth_user
    )

    assert find_public_blog_post_result.blog_post.identity == blog_post_record.identity
    assert find_public_blog_post_result.is_owner is False


async def test_find_public_blog_post_owner_private_post_returns_result_flagged_as_owner(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner_record = await insert_user_row(db_session)
    owner_auth_user = build_auth_user(user_id=owner_record.id, user_identity=owner_record.identity)
    persona_record = await insert_persona_row(db_session, created_by_id=owner_record.id)
    _, blog_post_record = await _insert_blog_post(
        db_session, created_by_id=owner_record.id, persona_id=persona_record.id
    )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    find_public_blog_post_result = await blog_post_service.find_public_blog_post(
        blog_post_record.identity, owner_auth_user
    )

    assert find_public_blog_post_result == PublicBlogPostResult(
        blog_post=BlogPostDetailResult(
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
        ),
        is_owner=True,
    )


@pytest.mark.parametrize(
    ("is_public", "published_at", "is_persona_public", "is_owner_active"),
    [
        pytest.param(False, datetime(2020, 1, 1, tzinfo=UTC), True, True, id="private_post"),
        pytest.param(True, None, True, True, id="unpublished_post"),
        pytest.param(True, datetime(2999, 1, 1, tzinfo=UTC), True, True, id="scheduled_post"),
        pytest.param(
            True, datetime(2020, 1, 1, tzinfo=UTC), False, True, id="public_post_private_persona"
        ),
        pytest.param(True, datetime(2020, 1, 1, tzinfo=UTC), True, False, id="suspended_creator"),
    ],
)
async def test_find_public_blog_post_signed_out_hidden_post_raises_not_found_exception(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    is_public: bool,
    published_at: datetime | None,
    is_persona_public: bool,
    is_owner_active: bool,
) -> None:
    owner_record = await insert_user_row(db_session, is_active=is_owner_active)
    persona_record = await insert_persona_row(
        db_session, created_by_id=owner_record.id, is_public=is_persona_public
    )
    _, blog_post_record = await _insert_blog_post(
        db_session,
        created_by_id=owner_record.id,
        persona_id=persona_record.id,
        is_public=is_public,
        published_at=published_at,
    )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    with pytest.raises(NotFoundException):
        await blog_post_service.find_public_blog_post(blog_post_record.identity, None)


async def test_find_public_blog_post_never_inserted_raises_not_found_exception(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    with pytest.raises(NotFoundException):
        await blog_post_service.find_public_blog_post(uuid4(), None)


async def test_find_public_blog_post_deleted_raises_not_found_exception(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner_record = await insert_user_row(db_session)
    persona_record = await insert_persona_row(
        db_session, created_by_id=owner_record.id, is_public=True
    )
    _, blog_post_record = await _insert_blog_post(
        db_session,
        created_by_id=owner_record.id,
        persona_id=persona_record.id,
        is_public=True,
        published_at=datetime(2020, 1, 1, tzinfo=UTC),
        deleted_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        deleted_by_id=owner_record.id,
    )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    with pytest.raises(NotFoundException):
        await blog_post_service.find_public_blog_post(blog_post_record.identity, None)


async def test_find_public_blog_post_another_users_private_post_raises_not_found_exception(
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
        await blog_post_service.find_public_blog_post(blog_post_record.identity, other_auth_user)


async def test_find_public_blog_post_another_users_published_post_inactive_creator_raises_not_found(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    suspended_owner_record = await insert_user_row(db_session, is_active=False)
    other_user_record = await insert_user_row(db_session)
    other_auth_user = build_auth_user(
        user_id=other_user_record.id, user_identity=other_user_record.identity
    )
    persona_record = await insert_persona_row(
        db_session, created_by_id=suspended_owner_record.id, is_public=True
    )
    _, blog_post_record = await _insert_blog_post(
        db_session,
        created_by_id=suspended_owner_record.id,
        persona_id=persona_record.id,
        is_public=True,
        published_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    with pytest.raises(NotFoundException):
        await blog_post_service.find_public_blog_post(blog_post_record.identity, other_auth_user)


async def test_find_public_blog_post_published_post_creator_reactivated_returns_result(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    owner_record = await insert_user_row(db_session, is_active=False)
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
    owner_record.is_active = True
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    find_public_blog_post_result = await blog_post_service.find_public_blog_post(
        blog_post_record.identity, None
    )

    assert find_public_blog_post_result.blog_post.identity == blog_post_record.identity


async def test_find_blog_post_others_published_post_inactive_creator_raises_not_found(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    suspended_owner_record = await insert_user_row(db_session, is_active=False)
    other_user_record = await insert_user_row(db_session)
    other_auth_user = build_auth_user(
        user_id=other_user_record.id, user_identity=other_user_record.identity
    )
    persona_record = await insert_persona_row(
        db_session, created_by_id=suspended_owner_record.id, is_public=True
    )
    _, blog_post_record = await _insert_blog_post(
        db_session,
        created_by_id=suspended_owner_record.id,
        persona_id=persona_record.id,
        is_public=True,
        published_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    with pytest.raises(NotFoundException):
        await blog_post_service.find_blog_post(blog_post_record.identity, other_auth_user)


async def test_find_blog_post_own_post_inactive_owner_returns_blog_post_detail_result(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    suspended_owner_record = await insert_user_row(db_session, is_active=False)
    owner_auth_user = build_auth_user(
        user_id=suspended_owner_record.id, user_identity=suspended_owner_record.identity
    )
    persona_record = await insert_persona_row(db_session, created_by_id=suspended_owner_record.id)
    _, blog_post_record = await _insert_blog_post(
        db_session, created_by_id=suspended_owner_record.id, persona_id=persona_record.id
    )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    find_blog_post_result = await blog_post_service.find_blog_post(
        blog_post_record.identity, owner_auth_user
    )

    assert find_blog_post_result.identity == blog_post_record.identity


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


async def test_update_blog_post_others_published_post_inactive_creator_raises_not_found(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    suspended_owner_record = await insert_user_row(db_session, is_active=False)
    other_user_record = await insert_user_row(db_session)
    other_auth_user = build_auth_user(
        user_id=other_user_record.id, user_identity=other_user_record.identity
    )
    persona_record = await insert_persona_row(
        db_session, created_by_id=suspended_owner_record.id, is_public=True
    )
    _, blog_post_record = await _insert_blog_post(
        db_session,
        created_by_id=suspended_owner_record.id,
        persona_id=persona_record.id,
        is_public=True,
        published_at=datetime(2020, 1, 1, tzinfo=UTC),
    )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    with pytest.raises(NotFoundException):
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


PAST_PUBLISHED_AT = datetime(2020, 1, 1, tzinfo=UTC)
FUTURE_PUBLISHED_AT = datetime(2099, 1, 1, tzinfo=UTC)


def _find_blog_post_titles(
    find_public_blog_post_list_result: FindPublicBlogPostListResult,
) -> list[str]:
    return [
        blog_post_summary_result.title
        for blog_post_summary_result in find_public_blog_post_list_result.blog_posts
    ]


async def test_find_public_blog_post_list_signed_out_returns_published_public_posts(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    author_record = await insert_user_row(db_session)
    persona_record = await insert_persona_row(
        db_session, created_by_id=author_record.id, is_public=True
    )
    _, blog_post_record = await _insert_blog_post(
        db_session,
        created_by_id=author_record.id,
        persona_id=persona_record.id,
        title="A Public Post",
        subtitle="A Subtitle",
        is_public=True,
        published_at=PAST_PUBLISHED_AT,
    )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    find_public_blog_post_list_result = await blog_post_service.find_public_blog_post_list(
        build_find_public_blog_post_list_input(page_size=5), None
    )

    assert find_public_blog_post_list_result == FindPublicBlogPostListResult(
        blog_posts=[
            BlogPostSummaryResult(
                identity=blog_post_record.identity,
                title="A Public Post",
                subtitle="A Subtitle",
                created_at=blog_post_record.created_at,
                updated_at=blog_post_record.updated_at,
                content_item=BlogPostContentItemResult(
                    is_public=True,
                    published_at=PAST_PUBLISHED_AT,
                    persona=BlogPostPersonaResult(identity=persona_record.identity),
                ),
            )
        ],
        page_info=PageInfoResult(page=1, page_size=5, total=1),
    )


@pytest.mark.parametrize(
    ("is_persona_public", "is_public", "published_at", "is_creator_active", "is_deleted"),
    [
        pytest.param(True, False, PAST_PUBLISHED_AT, True, False, id="private_post"),
        pytest.param(True, True, None, True, False, id="draft"),
        pytest.param(True, True, FUTURE_PUBLISHED_AT, True, False, id="scheduled_post"),
        pytest.param(False, True, PAST_PUBLISHED_AT, True, False, id="private_persona"),
        pytest.param(True, True, PAST_PUBLISHED_AT, False, False, id="inactive_creator"),
        pytest.param(True, True, PAST_PUBLISHED_AT, True, True, id="deleted_post"),
    ],
)
async def test_find_public_blog_post_list_signed_out_hidden_post_is_excluded(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    is_persona_public: bool,
    is_public: bool,
    published_at: datetime | None,
    is_creator_active: bool,
    is_deleted: bool,
) -> None:
    author_record = await insert_user_row(db_session, is_active=is_creator_active)
    persona_record = await insert_persona_row(
        db_session, created_by_id=author_record.id, is_public=is_persona_public
    )
    await _insert_blog_post(
        db_session,
        created_by_id=author_record.id,
        persona_id=persona_record.id,
        is_public=is_public,
        published_at=published_at,
        deleted_at=datetime(2026, 1, 4, tzinfo=UTC) if is_deleted else None,
        deleted_by_id=author_record.id if is_deleted else None,
    )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    find_public_blog_post_list_result = await blog_post_service.find_public_blog_post_list(
        build_find_public_blog_post_list_input(), None
    )

    assert find_public_blog_post_list_result.blog_posts == []
    assert find_public_blog_post_list_result.page_info.total == 0


async def test_find_public_blog_post_list_signed_in_includes_own_hidden_posts(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    public_persona_record = await insert_persona_row(
        db_session, created_by_id=user_record.id, is_public=True
    )
    private_persona_record = await insert_persona_row(
        db_session, created_by_id=user_record.id, is_public=False
    )
    await _insert_blog_post(
        db_session,
        created_by_id=user_record.id,
        persona_id=public_persona_record.id,
        title="Published",
        is_public=True,
        published_at=PAST_PUBLISHED_AT,
    )
    await _insert_blog_post(
        db_session,
        created_by_id=user_record.id,
        persona_id=public_persona_record.id,
        title="Draft",
        is_public=True,
    )
    await _insert_blog_post(
        db_session,
        created_by_id=user_record.id,
        persona_id=public_persona_record.id,
        title="Private",
        published_at=datetime(2019, 1, 1, tzinfo=UTC),
    )
    await _insert_blog_post(
        db_session,
        created_by_id=user_record.id,
        persona_id=private_persona_record.id,
        title="Under Private Persona",
        published_at=datetime(2018, 1, 1, tzinfo=UTC),
    )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    find_public_blog_post_list_result = await blog_post_service.find_public_blog_post_list(
        build_find_public_blog_post_list_input(), auth_user
    )

    blog_post_titles = _find_blog_post_titles(find_public_blog_post_list_result)
    assert blog_post_titles == ["Published", "Private", "Under Private Persona", "Draft"]
    assert find_public_blog_post_list_result.page_info.total == 4


async def test_find_public_blog_post_list_signed_in_as_another_user_excludes_their_hidden_posts(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    viewer_record = await insert_user_row(db_session)
    viewer_auth_user = build_auth_user(
        user_id=viewer_record.id, user_identity=viewer_record.identity
    )
    author_record = await insert_user_row(db_session)
    persona_record = await insert_persona_row(
        db_session, created_by_id=author_record.id, is_public=True
    )
    await _insert_blog_post(
        db_session,
        created_by_id=author_record.id,
        persona_id=persona_record.id,
        title="Author Published",
        is_public=True,
        published_at=PAST_PUBLISHED_AT,
    )
    await _insert_blog_post(
        db_session,
        created_by_id=author_record.id,
        persona_id=persona_record.id,
        title="Author Draft",
        is_public=True,
    )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    find_public_blog_post_list_result = await blog_post_service.find_public_blog_post_list(
        build_find_public_blog_post_list_input(), viewer_auth_user
    )

    assert _find_blog_post_titles(find_public_blog_post_list_result) == ["Author Published"]


async def _insert_public_posts(
    db_session: AsyncSession,
    *,
    titles: list[str],
    published_at: datetime = PAST_PUBLISHED_AT,
) -> None:
    author_record = await insert_user_row(db_session)
    persona_record = await insert_persona_row(
        db_session, created_by_id=author_record.id, is_public=True
    )
    for title in titles:
        await _insert_blog_post(
            db_session,
            created_by_id=author_record.id,
            persona_id=persona_record.id,
            title=title,
            is_public=True,
            published_at=published_at,
        )
    await db_session.commit()


async def test_find_public_blog_post_list_total_counts_every_row_and_pages_slice_them(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _insert_public_posts(
        db_session, titles=["Post 1", "Post 2", "Post 3", "Post 4", "Post 5"]
    )
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    find_public_blog_post_list_result = await blog_post_service.find_public_blog_post_list(
        build_find_public_blog_post_list_input(page=2, page_size=2), None
    )

    assert _find_blog_post_titles(find_public_blog_post_list_result) == ["Post 3", "Post 2"]
    assert find_public_blog_post_list_result.page_info == PageInfoResult(
        page=2, page_size=2, total=5
    )


async def test_find_public_blog_post_list_page_past_the_end_returns_no_rows_and_same_total(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _insert_public_posts(db_session, titles=["Post 1", "Post 2", "Post 3"])
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    find_public_blog_post_list_result = await blog_post_service.find_public_blog_post_list(
        build_find_public_blog_post_list_input(page=3, page_size=2), None
    )

    assert find_public_blog_post_list_result == FindPublicBlogPostListResult(
        blog_posts=[], page_info=PageInfoResult(page=3, page_size=2, total=3)
    )


async def test_find_public_blog_post_list_tied_sort_values_page_without_overlap_or_gaps(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _insert_public_posts(
        db_session, titles=["Tied 1", "Tied 2", "Tied 3", "Tied 4", "Tied 5"]
    )
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)
    paged_titles: list[str] = []

    for page in (1, 2, 3):
        find_public_blog_post_list_result = await blog_post_service.find_public_blog_post_list(
            build_find_public_blog_post_list_input(page=page, page_size=2), None
        )
        paged_titles += _find_blog_post_titles(find_public_blog_post_list_result)

    assert paged_titles == ["Tied 5", "Tied 4", "Tied 3", "Tied 2", "Tied 1"]


async def test_find_public_blog_post_list_tied_sort_values_ascending_break_ties_by_id_ascending(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _insert_public_posts(db_session, titles=["Tied 1", "Tied 2", "Tied 3"])
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    find_public_blog_post_list_result = await blog_post_service.find_public_blog_post_list(
        build_find_public_blog_post_list_input(sort_direction=SortDirectionType.ASC), None
    )

    assert _find_blog_post_titles(find_public_blog_post_list_result) == [
        "Tied 1",
        "Tied 2",
        "Tied 3",
    ]


@pytest.mark.parametrize(
    ("sort_direction", "expected_titles"),
    [
        pytest.param(SortDirectionType.DESC, ["Newest", "Oldest", "Draft"], id="descending"),
        pytest.param(SortDirectionType.ASC, ["Oldest", "Newest", "Draft"], id="ascending"),
    ],
)
async def test_find_public_blog_post_list_sorted_by_published_at_puts_null_last(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    sort_direction: SortDirectionType,
    expected_titles: list[str],
) -> None:
    user_record = await insert_user_row(db_session)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    persona_record = await insert_persona_row(
        db_session, created_by_id=user_record.id, is_public=True
    )
    for title, published_at in [
        ("Draft", None),
        ("Oldest", datetime(2020, 1, 1, tzinfo=UTC)),
        ("Newest", datetime(2021, 1, 1, tzinfo=UTC)),
    ]:
        await _insert_blog_post(
            db_session,
            created_by_id=user_record.id,
            persona_id=persona_record.id,
            title=title,
            is_public=True,
            published_at=published_at,
        )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    find_public_blog_post_list_result = await blog_post_service.find_public_blog_post_list(
        build_find_public_blog_post_list_input(
            sort_by=PublicBlogPostSortType.PUBLISHED_AT, sort_direction=sort_direction
        ),
        auth_user,
    )

    assert _find_blog_post_titles(find_public_blog_post_list_result) == expected_titles


@pytest.mark.parametrize(
    ("sort_direction", "expected_titles"),
    [
        pytest.param(SortDirectionType.ASC, ["Apple", "Banana", "Cherry"], id="ascending"),
        pytest.param(SortDirectionType.DESC, ["Cherry", "Banana", "Apple"], id="descending"),
    ],
)
async def test_find_public_blog_post_list_sorted_by_title(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    sort_direction: SortDirectionType,
    expected_titles: list[str],
) -> None:
    await _insert_public_posts(db_session, titles=["Banana", "Cherry", "Apple"])
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    find_public_blog_post_list_result = await blog_post_service.find_public_blog_post_list(
        build_find_public_blog_post_list_input(
            sort_by=PublicBlogPostSortType.TITLE, sort_direction=sort_direction
        ),
        None,
    )

    assert _find_blog_post_titles(find_public_blog_post_list_result) == expected_titles


async def test_find_public_blog_post_list_persona_identity_limits_rows_to_that_persona(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    author_record = await insert_user_row(db_session)
    matching_persona_record = await insert_persona_row(
        db_session, created_by_id=author_record.id, is_public=True
    )
    other_persona_record = await insert_persona_row(
        db_session, created_by_id=author_record.id, is_public=True
    )
    for persona_record, title in [
        (matching_persona_record, "Matching Post"),
        (other_persona_record, "Other Persona Post"),
    ]:
        await _insert_blog_post(
            db_session,
            created_by_id=author_record.id,
            persona_id=persona_record.id,
            title=title,
            is_public=True,
            published_at=PAST_PUBLISHED_AT,
        )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    find_public_blog_post_list_result = await blog_post_service.find_public_blog_post_list(
        build_find_public_blog_post_list_input(persona_identity=matching_persona_record.identity),
        None,
    )

    assert _find_blog_post_titles(find_public_blog_post_list_result) == ["Matching Post"]
    assert find_public_blog_post_list_result.page_info.total == 1


async def test_find_public_blog_post_list_without_persona_identity_lists_across_personas(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    author_record = await insert_user_row(db_session)
    for title in ["First Persona Post", "Second Persona Post"]:
        persona_record = await insert_persona_row(
            db_session, created_by_id=author_record.id, is_public=True
        )
        await _insert_blog_post(
            db_session,
            created_by_id=author_record.id,
            persona_id=persona_record.id,
            title=title,
            is_public=True,
            published_at=PAST_PUBLISHED_AT,
        )
    await db_session.commit()
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    find_public_blog_post_list_result = await blog_post_service.find_public_blog_post_list(
        build_find_public_blog_post_list_input(sort_by=PublicBlogPostSortType.TITLE), None
    )

    assert _find_blog_post_titles(find_public_blog_post_list_result) == [
        "Second Persona Post",
        "First Persona Post",
    ]


async def _insert_searchable_posts(
    db_session: AsyncSession, *, posts: list[tuple[str, str | None, str]]
) -> None:
    author_record = await insert_user_row(db_session)
    persona_record = await insert_persona_row(
        db_session, created_by_id=author_record.id, is_public=True
    )
    for title, subtitle, body in posts:
        await _insert_blog_post(
            db_session,
            created_by_id=author_record.id,
            persona_id=persona_record.id,
            title=title,
            subtitle=subtitle,
            body=body,
            is_public=True,
            published_at=PAST_PUBLISHED_AT,
        )
    await db_session.commit()


@pytest.mark.parametrize(
    ("search", "expected_titles"),
    [
        pytest.param("COFFEE", ["Morning Coffee"], id="title_case_insensitive"),
        pytest.param("brewing", ["Morning Coffee"], id="subtitle"),
        pytest.param("Coffee brewing", ["Morning Coffee"], id="words_across_title_and_subtitle"),
        pytest.param("coffee tea", [], id="every_word_must_match"),
        pytest.param("zebra", [], id="word_only_in_body"),
        pytest.param("  \t ", ["Morning Coffee", "Evening Tea"], id="whitespace_only"),
    ],
)
async def test_find_public_blog_post_list_search_matches_title_and_subtitle(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    search: str,
    expected_titles: list[str],
) -> None:
    await _insert_searchable_posts(
        db_session,
        posts=[
            ("Morning Coffee", "Slow brewing", "A body mentioning a zebra."),
            ("Evening Tea", None, "A body about leaves."),
        ],
    )
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    find_public_blog_post_list_result = await blog_post_service.find_public_blog_post_list(
        build_find_public_blog_post_list_input(search=search, sort_by=PublicBlogPostSortType.TITLE),
        None,
    )

    assert _find_blog_post_titles(find_public_blog_post_list_result) == expected_titles


@pytest.mark.parametrize(
    ("search", "expected_titles"),
    [
        pytest.param("%", ["100% Sure"], id="percent"),
        pytest.param("_", ["snake_case"], id="underscore"),
    ],
)
async def test_find_public_blog_post_list_search_wildcard_characters_match_literally(
    db_session: AsyncSession,
    db_session_factory: async_sessionmaker[AsyncSession],
    search: str,
    expected_titles: list[str],
) -> None:
    await _insert_searchable_posts(
        db_session,
        posts=[
            ("100% Sure", None, "Body."),
            ("snake_case", None, "Body."),
            ("Plain Title", None, "Body."),
        ],
    )
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    find_public_blog_post_list_result = await blog_post_service.find_public_blog_post_list(
        build_find_public_blog_post_list_input(search=search), None
    )

    assert _find_blog_post_titles(find_public_blog_post_list_result) == expected_titles


async def test_find_public_blog_post_list_search_uses_only_the_first_eight_words(
    db_session: AsyncSession, db_session_factory: async_sessionmaker[AsyncSession]
) -> None:
    await _insert_searchable_posts(db_session, posts=[("a b c d e f g h", None, "Body.")])
    blog_post_service = _build_blog_post_service(db_session, db_session_factory)

    find_public_blog_post_list_result = await blog_post_service.find_public_blog_post_list(
        build_find_public_blog_post_list_input(search="a b c d e f g h missing"), None
    )

    assert _find_blog_post_titles(find_public_blog_post_list_result) == ["a b c d e f g h"]
