import pytest
from pydantic import BaseModel

from libs.admin.constants import (
    ADMIN_CREDIT_LEDGER_PAGINATION_CONFIG,
    ADMIN_INVITE_PAGINATION_CONFIG,
    ADMIN_USER_PAGINATION_CONFIG,
)
from libs.admin.inputs import (
    AdminFindInvitePageInput,
    AdminFindUserCreditLedgerPageInput,
    AdminFindUserPageInput,
)
from libs.blog_posts.constants import (
    PUBLIC_BLOG_POST_PAGINATION_CONFIG,
    USER_BLOG_POST_PAGINATION_CONFIG,
)
from libs.blog_posts.inputs import FindPublicBlogPostPageInput, FindUserBlogPostPageInput
from libs.database.pagination_config import PaginationConfig
from libs.personas.constants import USER_PERSONA_PAGINATION_CONFIG
from libs.personas.inputs import FindUserPersonaPageInput


@pytest.mark.parametrize(
    ("pagination_config", "page_input_class"),
    [
        pytest.param(
            PUBLIC_BLOG_POST_PAGINATION_CONFIG,
            FindPublicBlogPostPageInput,
            id="public_blog_post_page",
        ),
        pytest.param(
            USER_BLOG_POST_PAGINATION_CONFIG,
            FindUserBlogPostPageInput,
            id="user_blog_post_page",
        ),
        pytest.param(
            USER_PERSONA_PAGINATION_CONFIG, FindUserPersonaPageInput, id="user_persona_page"
        ),
        pytest.param(ADMIN_USER_PAGINATION_CONFIG, AdminFindUserPageInput, id="admin_user_page"),
        pytest.param(
            ADMIN_INVITE_PAGINATION_CONFIG, AdminFindInvitePageInput, id="admin_invite_page"
        ),
        pytest.param(
            ADMIN_CREDIT_LEDGER_PAGINATION_CONFIG,
            AdminFindUserCreditLedgerPageInput,
            id="admin_credit_ledger_page",
        ),
    ],
)
def test_pagination_config_filter_keys_are_fields_of_the_page_input(
    pagination_config: PaginationConfig, page_input_class: type[BaseModel]
) -> None:
    filter_names = set(pagination_config.filters)

    assert filter_names <= set(page_input_class.model_fields)
