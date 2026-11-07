from libs.blog_posts.inputs import FindPublicBlogPostPageInput, FindUserBlogPostPageInput
from libs.blog_posts.types import PublicBlogPostSortType, UserBlogPostSortType
from libs.core.types import FilterOperatorType
from libs.database.orm import BlogPostOrm, ContentItemEngagementOrm, ContentItemOrm, PersonaOrm
from libs.database.pagination_config import PaginationConfig, PaginationFilterConfig

USER_BLOG_POST_PAGINATION_CONFIG = PaginationConfig(
    page_input_class=FindUserBlogPostPageInput,
    search_columns=(BlogPostOrm.title, BlogPostOrm.subtitle),
    sort_columns={
        UserBlogPostSortType.CREATED_AT: ContentItemOrm.created_at,
        UserBlogPostSortType.PUBLISHED_AT: ContentItemOrm.published_at,
        UserBlogPostSortType.TITLE: BlogPostOrm.title,
    },
    filters={
        "persona_identity": PaginationFilterConfig(PersonaOrm.identity, FilterOperatorType.EQUALS)
    },
    tiebreak_column=BlogPostOrm.id,
)

PUBLIC_BLOG_POST_PAGINATION_CONFIG = PaginationConfig(
    page_input_class=FindPublicBlogPostPageInput,
    search_columns=(BlogPostOrm.title, BlogPostOrm.subtitle, PersonaOrm.name),
    sort_columns={
        PublicBlogPostSortType.FEED_SCORE: ContentItemEngagementOrm.feed_score,
        PublicBlogPostSortType.PUBLISHED_AT: ContentItemOrm.published_at,
        PublicBlogPostSortType.TITLE: BlogPostOrm.title,
    },
    filters={
        "persona_identity": PaginationFilterConfig(PersonaOrm.identity, FilterOperatorType.EQUALS)
    },
    tiebreak_column=BlogPostOrm.id,
)
