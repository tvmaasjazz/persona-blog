from libs.blog_posts.types import PublicBlogPostSortType
from libs.core.types import FilterOperatorType
from libs.database.orm import BlogPostOrm, ContentItemOrm, PersonaOrm
from libs.database.pagination_config import PaginationConfig, PaginationFilterConfig

PUBLIC_BLOG_POST_PAGINATION_CONFIG = PaginationConfig(
    search_columns=(BlogPostOrm.title, BlogPostOrm.subtitle),
    sort_columns={
        PublicBlogPostSortType.PUBLISHED_AT: ContentItemOrm.published_at,
        PublicBlogPostSortType.TITLE: BlogPostOrm.title,
    },
    filters={
        "persona_identity": PaginationFilterConfig(PersonaOrm.identity, FilterOperatorType.EQUALS)
    },
    tiebreak_column=BlogPostOrm.id,
)
