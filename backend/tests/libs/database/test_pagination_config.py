from collections.abc import Mapping
from enum import StrEnum
from typing import Any

import pytest
from sqlalchemy.orm import QueryableAttribute

from libs.core.inputs import BasePageInput
from libs.core.types import FilterOperatorType
from libs.database.orm import UserOrm
from libs.database.pagination_config import PaginationConfig, PaginationFilterConfig


class UserSortType(StrEnum):
    EMAIL = "EMAIL"
    CREATED_AT = "CREATED_AT"


class OtherSortType(StrEnum):
    NAME = "NAME"


class UserPageInput(BasePageInput):
    sort_by: UserSortType
    email: str | None


class UnsortedPageInput(BasePageInput):
    pass


class NotEnumSortedPageInput(BasePageInput):
    sort_by: str


EMAIL_FILTER = PaginationFilterConfig(UserOrm.email, FilterOperatorType.EQUALS)
USER_SORT_COLUMNS: Mapping[StrEnum, QueryableAttribute[Any]] = {
    UserSortType.EMAIL: UserOrm.email,
    UserSortType.CREATED_AT: UserOrm.created_at,
}


def _build_pagination_config(
    *,
    page_input_class: type[BasePageInput] = UserPageInput,
    sort_columns: Mapping[StrEnum, QueryableAttribute[Any]] = USER_SORT_COLUMNS,
    filters: Mapping[str, PaginationFilterConfig] | None = None,
) -> PaginationConfig:
    return PaginationConfig(
        page_input_class=page_input_class,
        search_columns=(UserOrm.email,),
        sort_columns=sort_columns,
        filters={"email": EMAIL_FILTER} if filters is None else filters,
        tiebreak_column=UserOrm.id,
    )


def test_pagination_config_matching_its_input_class_builds() -> None:
    pagination_config = _build_pagination_config()

    assert pagination_config.page_input_class is UserPageInput


@pytest.mark.parametrize(
    ("sort_columns", "expected_message"),
    [
        pytest.param(
            {UserSortType.EMAIL: UserOrm.email},
            "keyed by exactly the values of UserSortType",
            id="sort_value_without_a_column",
        ),
        pytest.param(
            {**USER_SORT_COLUMNS, OtherSortType.NAME: UserOrm.display_name},
            "keyed by exactly the values of UserSortType",
            id="column_keyed_by_a_value_not_in_the_sort_type",
        ),
    ],
)
def test_pagination_config_sort_columns_not_matching_the_sort_type_raises(
    sort_columns: Mapping[StrEnum, QueryableAttribute[Any]], expected_message: str
) -> None:
    with pytest.raises(ValueError, match=expected_message):
        _build_pagination_config(sort_columns=sort_columns)


@pytest.mark.parametrize(
    "filters",
    [
        pytest.param({}, id="filter_field_without_a_filter"),
        pytest.param(
            {"email": EMAIL_FILTER, "display_name": EMAIL_FILTER},
            id="filter_that_is_not_a_field",
        ),
    ],
)
def test_pagination_config_filters_not_matching_the_input_fields_raises(
    filters: Mapping[str, PaginationFilterConfig],
) -> None:
    with pytest.raises(ValueError, match=r"filter fields: \['email'\]"):
        _build_pagination_config(filters=filters)


@pytest.mark.parametrize(
    "page_input_class",
    [
        pytest.param(UnsortedPageInput, id="sort_by_not_overridden"),
        pytest.param(NotEnumSortedPageInput, id="sort_by_not_an_enum"),
    ],
)
def test_pagination_config_input_without_a_sort_enum_raises(
    page_input_class: type[BasePageInput],
) -> None:
    with pytest.raises(ValueError, match="sort_by must be typed as a StrEnum"):
        _build_pagination_config(page_input_class=page_input_class, sort_columns={}, filters={})
