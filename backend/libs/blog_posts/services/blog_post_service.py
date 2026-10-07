from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.auth.results import AuthUser
from libs.blog_posts.inputs import CreateBlogPostInput, UpdateBlogPostInput
from libs.blog_posts.results import (
    BlogPostDetailResult,
    CreateBlogPostResult,
    FindUserBlogPostListResult,
)
from libs.content_items.inputs import CreateContentItemInput, UpdateContentItemInput
from libs.content_items.services import ContentItemService
from libs.content_items.types import ContentType
from libs.content_items.utils.content_item_query_utils import ContentItemQueryUtils
from libs.core.exceptions import ForbiddenException, NotFoundException
from libs.database.orm import BlogPostOrm, ContentItemOrm, PersonaOrm
from libs.personas.services import PersonaService


class BlogPostService:
    def __init__(
        self,
        db_session: AsyncSession,
        content_item_service: ContentItemService,
        persona_service: PersonaService,
    ) -> None:
        self._db_session = db_session
        self._content_item_service = content_item_service
        self._persona_service = persona_service

    async def create_blog_post(
        self, create_blog_post_input: CreateBlogPostInput, auth_user: AuthUser
    ) -> CreateBlogPostResult:
        find_user_persona_result = await self._persona_service.find_user_persona(
            create_blog_post_input.persona_identity, auth_user
        )
        create_content_item_result = await self._content_item_service.create_content_item(
            CreateContentItemInput(
                persona_id=find_user_persona_result.id,
                content_type=ContentType.BLOG_POST,
                is_public=create_blog_post_input.is_public,
                published_at=create_blog_post_input.published_at,
            ),
            auth_user,
        )
        blog_post_record = BlogPostOrm(
            content_item_id=create_content_item_result.id,
            title=create_blog_post_input.title,
            subtitle=create_blog_post_input.subtitle,
            body=create_blog_post_input.body,
            created_by_id=auth_user.id,
            updated_by_id=auth_user.id,
        )
        self._db_session.add(blog_post_record)
        await self._db_session.flush()

        if create_blog_post_input.generate_text_run_identity is not None:
            await self._content_item_service.link_generate_text_run(
                create_content_item_result.id, create_blog_post_input.generate_text_run_identity
            )

        return CreateBlogPostResult(identity=blog_post_record.identity)

    async def find_blog_post(
        self, blog_post_identity: UUID, auth_user: AuthUser
    ) -> BlogPostDetailResult:
        query = (
            select(
                BlogPostOrm.identity.label("identity"),
                PersonaOrm.identity.label("persona_identity"),
                BlogPostOrm.title.label("title"),
                BlogPostOrm.subtitle.label("subtitle"),
                BlogPostOrm.body.label("body"),
                ContentItemOrm.is_public.label("is_public"),
                ContentItemOrm.published_at.label("published_at"),
                BlogPostOrm.created_at.label("created_at"),
                BlogPostOrm.updated_at.label("updated_at"),
            )
            .join(ContentItemOrm, BlogPostOrm.content_item_id == ContentItemOrm.id)
            .join(PersonaOrm, ContentItemOrm.persona_id == PersonaOrm.id)
            .where(
                BlogPostOrm.identity == blog_post_identity,
                ContentItemQueryUtils.build_accessible_condition(auth_user.id),
            )
        )
        query_result = await self._db_session.execute(query)
        blog_post_row = query_result.mappings().one_or_none()

        if blog_post_row is None:
            raise NotFoundException("Blog post not found")
        return BlogPostDetailResult(**blog_post_row)

    async def find_user_blog_post_list(
        self, auth_user: AuthUser, persona_identity: UUID | None
    ) -> FindUserBlogPostListResult:
        query = (
            select(
                BlogPostOrm.identity.label("identity"),
                PersonaOrm.identity.label("persona_identity"),
                BlogPostOrm.title.label("title"),
                BlogPostOrm.subtitle.label("subtitle"),
                BlogPostOrm.body.label("body"),
                ContentItemOrm.is_public.label("is_public"),
                ContentItemOrm.published_at.label("published_at"),
                BlogPostOrm.created_at.label("created_at"),
                BlogPostOrm.updated_at.label("updated_at"),
            )
            .join(ContentItemOrm, BlogPostOrm.content_item_id == ContentItemOrm.id)
            .join(PersonaOrm, ContentItemOrm.persona_id == PersonaOrm.id)
            .where(ContentItemQueryUtils.build_owned_condition(auth_user.id))
            .order_by(ContentItemOrm.created_at.desc())
        )
        if persona_identity is not None:
            query = query.where(PersonaOrm.identity == persona_identity)

        query_result = await self._db_session.execute(query)
        blog_post_rows = query_result.mappings().all()

        return FindUserBlogPostListResult(
            blog_posts=[BlogPostDetailResult(**blog_post_row) for blog_post_row in blog_post_rows]
        )

    async def update_blog_post(
        self,
        blog_post_identity: UUID,
        update_blog_post_input: UpdateBlogPostInput,
        auth_user: AuthUser,
    ) -> None:
        blog_post_record = await self._find_owned_blog_post_record(blog_post_identity, auth_user)
        blog_post_record.title = update_blog_post_input.title
        blog_post_record.subtitle = update_blog_post_input.subtitle
        blog_post_record.body = update_blog_post_input.body
        blog_post_record.updated_by_id = auth_user.id
        await self._db_session.flush()

        await self._content_item_service.update_content_item(
            blog_post_record.content_item_id,
            UpdateContentItemInput(
                is_public=update_blog_post_input.is_public,
                published_at=update_blog_post_input.published_at,
            ),
            auth_user,
        )

    async def delete_blog_post(self, blog_post_identity: UUID, auth_user: AuthUser) -> None:
        blog_post_record = await self._find_owned_blog_post_record(blog_post_identity, auth_user)
        blog_post_record.deleted_at = datetime.now(UTC)
        blog_post_record.deleted_by_id = auth_user.id
        await self._db_session.flush()

        await self._content_item_service.delete_content_item(
            blog_post_record.content_item_id, auth_user
        )

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
