from libs.blog_posts.types import PublicBlogPostSortType
from libs.core.types import FilterOperatorType
from libs.database.list_query_config import ListFilterConfig, ListQueryConfig
from libs.database.orm import BlogPostOrm, ContentItemOrm, PersonaOrm

PUBLIC_BLOG_POST_LIST_CONFIG = ListQueryConfig(
    search_columns=(BlogPostOrm.title, BlogPostOrm.subtitle),
    sort_columns={
        PublicBlogPostSortType.PUBLISHED_AT: ContentItemOrm.published_at,
        PublicBlogPostSortType.TITLE: BlogPostOrm.title,
    },
    filters={"persona_identity": ListFilterConfig(PersonaOrm.identity, FilterOperatorType.EQUALS)},
    tiebreak_column=BlogPostOrm.id,
)
