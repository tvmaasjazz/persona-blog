from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum

import pytest
from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.core.inputs import ListInput, PageInput
from libs.core.results import PageInfoResult
from libs.core.types import FilterOperatorType, SortDirectionType
from libs.database.list_query_config import ListFilterConfig, ListQueryConfig
from libs.database.orm import UserOrm
from libs.database.utils import PageQueryUtils
from tests.factories.core import build_page_input
from tests.factories.users import insert_user_row


class UserSortType(StrEnum):
    EMAIL = "EMAIL"
    CREDIT_BALANCE = "CREDIT_BALANCE"


class UserListInput(ListInput):
    sort_by: UserSortType = UserSortType.EMAIL
    email: str | None = None
    emails: list[str] | None = None
    min_credit_balance_usd: Decimal | None = None
    max_credit_balance_usd: Decimal | None = None
    has_last_login_at: bool | None = None


USER_LIST_CONFIG = ListQueryConfig(
    search_columns=(UserOrm.email, UserOrm.display_name),
    sort_columns={
        UserSortType.EMAIL: UserOrm.email,
        UserSortType.CREDIT_BALANCE: UserOrm.credit_balance_usd,
    },
    filters={
        "email": ListFilterConfig(UserOrm.email, FilterOperatorType.EQUALS),
        "emails": ListFilterConfig(UserOrm.email, FilterOperatorType.IN),
        "min_credit_balance_usd": ListFilterConfig(
            UserOrm.credit_balance_usd, FilterOperatorType.GTE
        ),
        "max_credit_balance_usd": ListFilterConfig(
            UserOrm.credit_balance_usd, FilterOperatorType.LT
        ),
        "has_last_login_at": ListFilterConfig(UserOrm.last_login_at, FilterOperatorType.HAS_VALUE),
    },
    tiebreak_column=UserOrm.id,
)


def _build_user_list_input(
    *,
    page_input: PageInput | None = None,
    sort_by: UserSortType = UserSortType.EMAIL,
    email: str | None = None,
    emails: list[str] | None = None,
    min_credit_balance_usd: Decimal | None = None,
    max_credit_balance_usd: Decimal | None = None,
    has_last_login_at: bool | None = None,
) -> UserListInput:
    return UserListInput(
        page_input=page_input or build_page_input(sort_direction=SortDirectionType.ASC),
        sort_by=sort_by,
        email=email,
        emails=emails,
        min_credit_balance_usd=min_credit_balance_usd,
        max_credit_balance_usd=max_credit_balance_usd,
        has_last_login_at=has_last_login_at,
    )


def _build_user_base_query() -> Select[tuple[UserOrm]]:
    return select(UserOrm).where(UserOrm.email.like("page-query-%"))


async def _insert_page_query_users(db_session: AsyncSession) -> None:
    await insert_user_row(
        db_session,
        email="page-query-a@example.com",
        credit_balance_usd=Decimal("1.00"),
        last_login_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    await insert_user_row(
        db_session,
        email="page-query-b@example.com",
        credit_balance_usd=Decimal("2.00"),
    )
    await insert_user_row(
        db_session,
        email="page-query-c@example.com",
        credit_balance_usd=Decimal("3.00"),
        last_login_at=datetime(2026, 1, 2, tzinfo=UTC),
    )
    await insert_user_row(db_session, email="other@example.com", credit_balance_usd=Decimal("9.00"))


async def _find_filtered_emails(
    db_session: AsyncSession, user_list_input: UserListInput
) -> list[str]:
    filtered_query = PageQueryUtils.build_filtered_query(
        _build_user_base_query(), USER_LIST_CONFIG, user_list_input
    )
    page_query = PageQueryUtils.build_page_query(filtered_query, USER_LIST_CONFIG, user_list_input)
    page_query_result = await db_session.execute(page_query)
    return [page_row[0].email for page_row in page_query_result.all()]


@pytest.mark.parametrize(
    ("user_list_input", "expected_emails"),
    [
        pytest.param(
            _build_user_list_input(email="page-query-b@example.com"),
            ["page-query-b@example.com"],
            id="equals",
        ),
        pytest.param(
            _build_user_list_input(emails=["page-query-a@example.com", "page-query-c@example.com"]),
            ["page-query-a@example.com", "page-query-c@example.com"],
            id="in",
        ),
        pytest.param(
            _build_user_list_input(min_credit_balance_usd=Decimal("2.00")),
            ["page-query-b@example.com", "page-query-c@example.com"],
            id="gte_includes_boundary",
        ),
        pytest.param(
            _build_user_list_input(max_credit_balance_usd=Decimal("2.00")),
            ["page-query-a@example.com"],
            id="lt_excludes_boundary",
        ),
        pytest.param(
            _build_user_list_input(has_last_login_at=True),
            ["page-query-a@example.com", "page-query-c@example.com"],
            id="has_value_true",
        ),
        pytest.param(
            _build_user_list_input(has_last_login_at=False),
            ["page-query-b@example.com"],
            id="has_value_false",
        ),
        pytest.param(
            _build_user_list_input(),
            ["page-query-a@example.com", "page-query-b@example.com", "page-query-c@example.com"],
            id="none_values_add_no_condition",
        ),
        pytest.param(
            _build_user_list_input(min_credit_balance_usd=Decimal("2.00"), has_last_login_at=True),
            ["page-query-c@example.com"],
            id="filters_combine_with_and",
        ),
    ],
)
async def test_build_filtered_query_applies_each_operator(
    db_session: AsyncSession, user_list_input: UserListInput, expected_emails: list[str]
) -> None:
    await _insert_page_query_users(db_session)

    filtered_emails = await _find_filtered_emails(db_session, user_list_input)

    assert filtered_emails == expected_emails


@pytest.mark.parametrize(
    ("search", "expected_emails"),
    [
        pytest.param("PAGE-QUERY-A", ["page-query-a@example.com"], id="single_word"),
        pytest.param("ada a@example", ["page-query-a@example.com"], id="word_in_other_column"),
        pytest.param("   ", ["page-query-a@example.com", "page-query-b@example.com"], id="blank"),
        pytest.param(None, ["page-query-a@example.com", "page-query-b@example.com"], id="unset"),
    ],
)
async def test_build_filtered_query_search_matches_any_search_column_for_every_word(
    db_session: AsyncSession, search: str | None, expected_emails: list[str]
) -> None:
    await insert_user_row(db_session, email="page-query-a@example.com", display_name="Ada Lovelace")
    await insert_user_row(db_session, email="page-query-b@example.com", display_name="Grace Hopper")
    base_query = _build_user_base_query()

    user_list_input = _build_user_list_input(page_input=build_page_input(search=search))

    filtered_query = PageQueryUtils.build_filtered_query(
        base_query, USER_LIST_CONFIG, user_list_input
    )

    filtered_query_result = await db_session.execute(filtered_query.order_by(UserOrm.email))
    filtered_emails = [user_record.email for user_record in filtered_query_result.scalars().all()]
    assert filtered_emails == expected_emails


@pytest.mark.parametrize(
    ("sort_by", "sort_direction", "expected_emails"),
    [
        pytest.param(
            UserSortType.EMAIL,
            SortDirectionType.ASC,
            ["page-query-a@example.com", "page-query-b@example.com", "page-query-c@example.com"],
            id="email_ascending",
        ),
        pytest.param(
            UserSortType.CREDIT_BALANCE,
            SortDirectionType.DESC,
            ["page-query-c@example.com", "page-query-b@example.com", "page-query-a@example.com"],
            id="credit_balance_descending",
        ),
    ],
)
async def test_build_page_query_orders_by_the_sort_column_in_the_direction(
    db_session: AsyncSession,
    sort_by: UserSortType,
    sort_direction: SortDirectionType,
    expected_emails: list[str],
) -> None:
    await _insert_page_query_users(db_session)
    user_list_input = _build_user_list_input(
        page_input=build_page_input(sort_direction=sort_direction), sort_by=sort_by
    )

    page_query = PageQueryUtils.build_page_query(
        _build_user_base_query(), USER_LIST_CONFIG, user_list_input
    )

    page_query_result = await db_session.execute(page_query)
    page_emails = [page_row[0].email for page_row in page_query_result.all()]
    assert page_emails == expected_emails


async def test_build_page_query_offset_is_page_minus_one_times_page_size(
    db_session: AsyncSession,
) -> None:
    for letter in "abcde":
        await insert_user_row(db_session, email=f"page-query-{letter}@example.com")
    user_list_input = _build_user_list_input(
        page_input=build_page_input(page=2, page_size=2, sort_direction=SortDirectionType.ASC)
    )

    page_query = PageQueryUtils.build_page_query(
        _build_user_base_query(), USER_LIST_CONFIG, user_list_input
    )

    page_query_result = await db_session.execute(page_query)
    page_emails = [page_row[0].email for page_row in page_query_result.all()]
    assert page_emails == ["page-query-c@example.com", "page-query-d@example.com"]


async def test_build_page_query_total_column_counts_all_filtered_rows_on_every_row_of_a_middle_page(
    db_session: AsyncSession,
) -> None:
    for letter in "abcde":
        await insert_user_row(db_session, email=f"page-query-{letter}@example.com")
    await insert_user_row(db_session, email="other@example.com")
    user_list_input = _build_user_list_input(
        page_input=build_page_input(page=2, page_size=2, sort_direction=SortDirectionType.ASC)
    )

    page_query = PageQueryUtils.build_page_query(
        _build_user_base_query(), USER_LIST_CONFIG, user_list_input
    )

    page_query_result = await db_session.execute(page_query)
    page_rows = page_query_result.all()
    assert [page_row[0].email for page_row in page_rows] == [
        "page-query-c@example.com",
        "page-query-d@example.com",
    ]
    assert [page_row.total for page_row in page_rows] == [5, 5]


async def test_build_page_query_equal_sort_values_break_ties_by_tiebreak_column_in_direction(
    db_session: AsyncSession,
) -> None:
    for letter in "abc":
        await insert_user_row(
            db_session, email=f"page-query-{letter}@example.com", credit_balance_usd=Decimal("1.00")
        )
    user_list_input = _build_user_list_input(
        page_input=build_page_input(sort_direction=SortDirectionType.DESC),
        sort_by=UserSortType.CREDIT_BALANCE,
    )

    page_query = PageQueryUtils.build_page_query(
        _build_user_base_query(), USER_LIST_CONFIG, user_list_input
    )

    page_query_result = await db_session.execute(page_query)
    page_emails = [page_row[0].email for page_row in page_query_result.all()]
    assert page_emails == [
        "page-query-c@example.com",
        "page-query-b@example.com",
        "page-query-a@example.com",
    ]


async def test_build_count_query_counts_every_matching_row(db_session: AsyncSession) -> None:
    await _insert_page_query_users(db_session)
    filtered_query = PageQueryUtils.build_filtered_query(
        _build_user_base_query(),
        USER_LIST_CONFIG,
        _build_user_list_input(min_credit_balance_usd=Decimal("2.00")),
    )

    count_query = PageQueryUtils.build_count_query(filtered_query)

    total = await db_session.scalar(count_query)
    assert total == 2


def test_build_count_query_ignores_ordering() -> None:
    ordered_query = _build_user_base_query().order_by(UserOrm.email.desc())

    count_query = PageQueryUtils.build_count_query(ordered_query)

    assert "ORDER BY" not in str(count_query)


@pytest.mark.parametrize(
    ("page", "page_size", "total"),
    [
        pytest.param(1, 20, 0, id="empty"),
        pytest.param(3, 10, 25, id="last_partial_page"),
        pytest.param(9, 10, 25, id="past_the_end"),
    ],
)
def test_build_page_info_echoes_page_page_size_and_total(
    page: int, page_size: int, total: int
) -> None:
    page_input = build_page_input(page=page, page_size=page_size)

    page_info_result = PageQueryUtils.build_page_info(page_input, total)

    assert page_info_result == PageInfoResult(page=page, page_size=page_size, total=total)
