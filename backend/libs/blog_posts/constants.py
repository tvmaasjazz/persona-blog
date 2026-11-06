from libs.blog_posts.types import PublicBlogPostSortType
from libs.core.types import FilterOperatorType
from libs.database.list_query_spec import ListFilter, ListQuerySpec
from libs.database.orm import BlogPostOrm, ContentItemOrm, PersonaOrm

PUBLIC_BLOG_POST_LIST_SPEC = ListQuerySpec(
    search_columns=(BlogPostOrm.title, BlogPostOrm.subtitle),
    sort_columns={
        PublicBlogPostSortType.PUBLISHED_AT: ContentItemOrm.published_at,
        PublicBlogPostSortType.TITLE: BlogPostOrm.title,
    },
    filters={"persona_identity": ListFilter(PersonaOrm.identity, FilterOperatorType.EQUALS)},
    tiebreak_column=BlogPostOrm.id,
)
