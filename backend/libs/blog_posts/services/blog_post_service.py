from datetime import datetime
from uuid import UUID

from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from libs.auth.results import AuthUser
from libs.blog_posts.constants import PUBLIC_BLOG_POST_LIST_SPEC
from libs.blog_posts.exceptions import BlogPostGenerateTextRunOutputInvalidException
from libs.blog_posts.inputs import (
    CreateBlogPostFromGenerateTextRunInput,
    CreateBlogPostInput,
    FindPublicBlogPostListInput,
    UpdateBlogPostInput,
)
from libs.blog_posts.results import (
    BlogPostDetailResult,
    BlogPostSummaryResult,
    CreateBlogPostResult,
    FindPublicBlogPostListResult,
    FindUserBlogPostListResult,
    PublicBlogPostResult,
)
from libs.blog_posts.utils import BlogPostValidationUtils
from libs.content_items.inputs import CreateContentItemInput, UpdateContentItemInput
from libs.content_items.services import ContentItemService
from libs.content_items.types import ContentType
from libs.content_items.utils.content_item_query_utils import ContentItemQueryUtils
from libs.core.exceptions import ForbiddenException, NotFoundException
from libs.core.utils.markdown_utils import MarkdownUtils
from libs.database.orm import BlogPostOrm, ContentItemOrm, PersonaOrm
from libs.database.utils import DatabaseClockUtils, PageQueryUtils
from libs.generate_text.services import GenerateTextRunService, GenerateTextStepService
from libs.personas.services import PersonaService


class BlogPostService:
    """Creates, reads, updates and soft-deletes blog posts together with their content items."""

    def __init__(
        self,
        db_session: AsyncSession,
        content_item_service: ContentItemService,
        persona_service: PersonaService,
        generate_text_run_service: GenerateTextRunService,
        generate_text_step_service: GenerateTextStepService,
    ) -> None:
        self._db_session = db_session
        self._content_item_service = content_item_service
        self._persona_service = persona_service
        self._generate_text_run_service = generate_text_run_service
        self._generate_text_step_service = generate_text_step_service

    async def create_blog_post(
        self, create_blog_post_input: CreateBlogPostInput, auth_user: AuthUser
    ) -> CreateBlogPostResult:
        """Creates a post under one of the caller's own personas; NotFoundException for any other
        persona."""
        find_user_persona_result = await self._persona_service.find_user_persona(
            create_blog_post_input.persona_identity, auth_user
        )
        return await self._create_content_item_and_blog_post(
            persona_id=find_user_persona_result.id,
            title=create_blog_post_input.title,
            subtitle=create_blog_post_input.subtitle,
            body=create_blog_post_input.body,
            is_public=create_blog_post_input.is_public,
            published_at=create_blog_post_input.published_at,
            generate_text_run_identity=None,
            auth_user=auth_user,
        )

    async def create_blog_post_from_generate_text_run(
        self,
        create_blog_post_from_generate_text_run_input: CreateBlogPostFromGenerateTextRunInput,
        auth_user: AuthUser,
    ) -> CreateBlogPostResult:
        """Saves a run's latest output as a post, raising
        BlogPostGenerateTextRunOutputInvalidException when it isn't a valid post."""
        generate_text_run_identity = (
            create_blog_post_from_generate_text_run_input.generate_text_run_identity
        )
        find_run_result = await self._generate_text_run_service.find_run_by_identity(
            generate_text_run_identity
        )
        find_latest_step_result = await self._generate_text_step_service.find_latest_step(
            find_run_result.id
        )
        split_markdown_post_result = MarkdownUtils.split_post(find_latest_step_result.content)
        body_problems = BlogPostValidationUtils.find_body_problems(split_markdown_post_result.body)

        if (
            find_run_result.persona_id is None
            or split_markdown_post_result.title is None
            or not split_markdown_post_result.body
            or body_problems
        ):
            raise BlogPostGenerateTextRunOutputInvalidException(
                "Generate text run output is not a valid blog post"
            )

        return await self._create_content_item_and_blog_post(
            persona_id=find_run_result.persona_id,
            title=split_markdown_post_result.title,
            subtitle=split_markdown_post_result.subtitle,
            body=split_markdown_post_result.body,
            is_public=create_blog_post_from_generate_text_run_input.is_public,
            published_at=create_blog_post_from_generate_text_run_input.published_at,
            generate_text_run_identity=generate_text_run_identity,
            auth_user=auth_user,
        )

    async def find_blog_post(
        self, blog_post_identity: UUID, auth_user: AuthUser
    ) -> BlogPostDetailResult:
        """The caller's own post; NotFoundException for anyone else's, published or not."""
        query = (
            select(BlogPostOrm)
            .join(ContentItemOrm, BlogPostOrm.content_item_id == ContentItemOrm.id)
            .join(PersonaOrm, ContentItemOrm.persona_id == PersonaOrm.id)
            .where(
                BlogPostOrm.identity == blog_post_identity,
                ContentItemQueryUtils.build_owned_condition(auth_user.id),
            )
            .options(
                contains_eager(BlogPostOrm.content_item).contains_eager(ContentItemOrm.persona)
            )
        )
        query_result = await self._db_session.execute(query)
        blog_post_record = query_result.scalar_one_or_none()

        if blog_post_record is None:
            raise NotFoundException("Blog post not found")
        return BlogPostDetailResult.model_validate(blog_post_record, from_attributes=True)

    async def find_public_blog_post(
        self, blog_post_identity: UUID, auth_user: AuthUser | None
    ) -> PublicBlogPostResult:
        """The caller's own post or anyone's published public one, flagged with whether the
        caller owns it; NotFoundException otherwise."""
        auth_user_id = auth_user.id if auth_user is not None else None
        query = (
            select(BlogPostOrm)
            .join(ContentItemOrm, BlogPostOrm.content_item_id == ContentItemOrm.id)
            .join(PersonaOrm, ContentItemOrm.persona_id == PersonaOrm.id)
            .where(
                BlogPostOrm.identity == blog_post_identity,
                ContentItemQueryUtils.build_accessible_condition(auth_user_id),
            )
            .options(
                contains_eager(BlogPostOrm.content_item).contains_eager(ContentItemOrm.persona)
            )
        )
        query_result = await self._db_session.execute(query)
        blog_post_record = query_result.scalar_one_or_none()

        if blog_post_record is None:
            raise NotFoundException("Blog post not found")
        return PublicBlogPostResult(
            blog_post=BlogPostDetailResult.model_validate(blog_post_record, from_attributes=True),
            is_owner=auth_user_id is not None and blog_post_record.created_by_id == auth_user_id,
        )

    async def find_public_blog_post_list(
        self,
        find_public_blog_post_list_input: FindPublicBlogPostListInput,
        auth_user: AuthUser | None,
    ) -> FindPublicBlogPostListResult:
        """One page of published public posts of public personas, plus the caller's own posts
        drafts included, searched, filtered and sorted per the input."""
        auth_user_id = auth_user.id if auth_user is not None else None
        page_input = find_public_blog_post_list_input.page_input

        # Base query: the posts this caller may see
        base_query = (
            select(BlogPostOrm)
            .join(ContentItemOrm, BlogPostOrm.content_item_id == ContentItemOrm.id)
            .join(PersonaOrm, ContentItemOrm.persona_id == PersonaOrm.id)
            .where(ContentItemQueryUtils.build_accessible_condition(auth_user_id))
        )
        filtered_query = PageQueryUtils.build_filtered_query(
            base_query,
            PUBLIC_BLOG_POST_LIST_SPEC,
            find_public_blog_post_list_input,
            page_input,
        )

        # Count every matching row, then read the requested page
        count_query = PageQueryUtils.build_count_query(filtered_query)
        count_query_result = await self._db_session.execute(count_query)
        total = count_query_result.scalar_one()

        page_query = PageQueryUtils.build_page_query(
            filtered_query,
            PUBLIC_BLOG_POST_LIST_SPEC,
            find_public_blog_post_list_input.sort_by,
            page_input,
        ).options(contains_eager(BlogPostOrm.content_item).contains_eager(ContentItemOrm.persona))
        page_query_result = await self._db_session.execute(page_query)
        blog_post_records = page_query_result.scalars().all()

        return FindPublicBlogPostListResult(
            blog_posts=[
                BlogPostSummaryResult.model_validate(blog_post_record, from_attributes=True)
                for blog_post_record in blog_post_records
            ],
            page_info=PageQueryUtils.build_page_info(page_input, total),
        )

    async def find_user_blog_post_list(
        self, auth_user: AuthUser, persona_identity: UUID | None
    ) -> FindUserBlogPostListResult:
        """The caller's own posts, newest first, optionally limited to one persona."""
        query = (
            select(BlogPostOrm)
            .join(ContentItemOrm, BlogPostOrm.content_item_id == ContentItemOrm.id)
            .join(PersonaOrm, ContentItemOrm.persona_id == PersonaOrm.id)
            .where(ContentItemQueryUtils.build_owned_condition(auth_user.id))
            .order_by(ContentItemOrm.created_at.desc())
            .options(
                contains_eager(BlogPostOrm.content_item).contains_eager(ContentItemOrm.persona)
            )
        )
        if persona_identity is not None:
            query = query.where(PersonaOrm.identity == persona_identity)

        query_result = await self._db_session.execute(query)
        blog_post_records = query_result.scalars().all()

        return FindUserBlogPostListResult(
            blog_posts=[
                BlogPostDetailResult.model_validate(blog_post_record, from_attributes=True)
                for blog_post_record in blog_post_records
            ]
        )

    async def update_blog_post(
        self,
        blog_post_identity: UUID,
        update_blog_post_input: UpdateBlogPostInput,
        auth_user: AuthUser,
    ) -> None:
        """Updates the post and its content item; ForbiddenException unless the creator."""
        blog_post_record = await self._find_owned_blog_post_record(blog_post_identity, auth_user)
        blog_post_update = (
            update(BlogPostOrm)
            .where(BlogPostOrm.id == blog_post_record.id)
            .values(
                title=update_blog_post_input.title,
                subtitle=update_blog_post_input.subtitle,
                body=update_blog_post_input.body,
                updated_by_id=auth_user.id,
            )
        )
        await self._db_session.execute(blog_post_update)

        await self._content_item_service.update_content_item(
            blog_post_record.content_item_id,
            UpdateContentItemInput(
                is_public=update_blog_post_input.is_public,
                published_at=update_blog_post_input.published_at,
            ),
            auth_user,
        )

    async def delete_blog_post(self, blog_post_identity: UUID, auth_user: AuthUser) -> None:
        """Soft-deletes the post and its content item; ForbiddenException unless the creator."""
        blog_post_record = await self._find_owned_blog_post_record(blog_post_identity, auth_user)
        blog_post_soft_delete_update = (
            update(BlogPostOrm)
            .where(BlogPostOrm.id == blog_post_record.id)
            .values(
                deleted_at=DatabaseClockUtils.build_utc_now_sql(),
                deleted_by_id=auth_user.id,
            )
        )
        await self._db_session.execute(blog_post_soft_delete_update)

        await self._content_item_service.delete_content_item(
            blog_post_record.content_item_id, auth_user
        )

    async def _create_content_item_and_blog_post(
        self,
        persona_id: int,
        title: str,
        subtitle: str | None,
        body: str,
        is_public: bool,
        published_at: datetime | None,
        generate_text_run_identity: UUID | None,
        auth_user: AuthUser,
    ) -> CreateBlogPostResult:
        create_content_item_result = await self._content_item_service.create_content_item(
            CreateContentItemInput(
                persona_id=persona_id,
                content_type=ContentType.BLOG_POST,
                is_public=is_public,
                published_at=published_at,
                generate_text_run_identity=generate_text_run_identity,
            ),
            auth_user,
        )
        blog_post_insert = (
            insert(BlogPostOrm)
            .values(
                content_item_id=create_content_item_result.id,
                title=title,
                subtitle=subtitle,
                body=body,
                created_by_id=auth_user.id,
                updated_by_id=auth_user.id,
            )
            .returning(BlogPostOrm.identity)
        )
        blog_post_insert_result = await self._db_session.execute(blog_post_insert)
        blog_post_identity = blog_post_insert_result.scalar_one()

        return CreateBlogPostResult(identity=blog_post_identity)

    async def _find_accessible_blog_post_record(
        self, blog_post_identity: UUID, auth_user: AuthUser
    ) -> BlogPostOrm:
        query = (
            select(BlogPostOrm)
            .join(ContentItemOrm, BlogPostOrm.content_item_id == ContentItemOrm.id)
            .join(PersonaOrm, ContentItemOrm.persona_id == PersonaOrm.id)
            .where(
                BlogPostOrm.identity == blog_post_identity,
                ContentItemQueryUtils.build_accessible_condition(auth_user.id),
            )
        )
        query_result = await self._db_session.execute(query)
        blog_post_record = query_result.scalar_one_or_none()

        if blog_post_record is None:
            raise NotFoundException("Blog post not found")
        return blog_post_record

    async def _find_owned_blog_post_record(
        self, blog_post_identity: UUID, auth_user: AuthUser
    ) -> BlogPostOrm:
        blog_post_record = await self._find_accessible_blog_post_record(
            blog_post_identity, auth_user
        )
        if blog_post_record.created_by_id != auth_user.id:
            raise ForbiddenException("Only the blog post's creator can change it")
        return blog_post_record
