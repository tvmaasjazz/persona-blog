import pytest
from pydantic import BaseModel

from libs.blog_posts.constants import PUBLIC_BLOG_POST_PAGINATION_CONFIG
from libs.blog_posts.inputs import FindPublicBlogPostPageInput
from libs.database.pagination_config import PaginationConfig


@pytest.mark.parametrize(
    ("pagination_config", "page_input_class"),
    [
        pytest.param(
            PUBLIC_BLOG_POST_PAGINATION_CONFIG,
            FindPublicBlogPostPageInput,
            id="public_blog_post_page",
        ),
    ],
)
def test_pagination_config_filter_keys_are_fields_of_the_page_input(
    pagination_config: PaginationConfig, page_input_class: type[BaseModel]
) -> None:
    filter_names = set(pagination_config.filters)

    assert filter_names <= set(page_input_class.model_fields)
