import pytest
from pydantic import BaseModel

from libs.blog_posts.constants import PUBLIC_BLOG_POST_LIST_CONFIG
from libs.blog_posts.inputs import FindPublicBlogPostListInput
from libs.database.list_query_config import ListQueryConfig


@pytest.mark.parametrize(
    ("list_query_config", "list_input_class"),
    [
        pytest.param(
            PUBLIC_BLOG_POST_LIST_CONFIG, FindPublicBlogPostListInput, id="public_blog_post_list"
        ),
    ],
)
def test_list_query_config_filter_keys_are_fields_of_the_list_input(
    list_query_config: ListQueryConfig, list_input_class: type[BaseModel]
) -> None:
    filter_names = set(list_query_config.filters)

    assert filter_names <= set(list_input_class.model_fields)
