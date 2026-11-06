import pytest
from pydantic import BaseModel

from libs.blog_posts.constants import PUBLIC_BLOG_POST_LIST_SPEC
from libs.blog_posts.inputs import FindPublicBlogPostListInput
from libs.database.list_query_spec import ListQuerySpec


@pytest.mark.parametrize(
    ("list_query_spec", "list_input_class"),
    [
        pytest.param(
            PUBLIC_BLOG_POST_LIST_SPEC, FindPublicBlogPostListInput, id="public_blog_post_list"
        ),
    ],
)
def test_list_query_spec_filter_keys_are_fields_of_the_list_input(
    list_query_spec: ListQuerySpec, list_input_class: type[BaseModel]
) -> None:
    filter_names = set(list_query_spec.filters)

    assert filter_names <= set(list_input_class.model_fields)
