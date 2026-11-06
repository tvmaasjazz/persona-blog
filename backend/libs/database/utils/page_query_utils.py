from collections.abc import Callable
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, func, or_, select
from sqlalchemy.orm import QueryableAttribute
from sqlalchemy.sql.elements import UnaryExpression

from libs.core.inputs import ListInput, PageInput
from libs.core.results import PageInfoResult
from libs.core.types import FilterOperatorType, SortDirectionType
from libs.database.list_query_config import ListQueryConfig

MAX_SEARCH_WORD_COUNT = 8

CONDITION_BUILDER_BY_OPERATOR: dict[
    FilterOperatorType, Callable[[QueryableAttribute[Any], Any], ColumnElement[bool]]
] = {
    FilterOperatorType.EQUALS: lambda column, value: column == value,
    FilterOperatorType.IN: lambda column, value: column.in_(value),
    FilterOperatorType.GTE: lambda column, value: column >= value,
    FilterOperatorType.LT: lambda column, value: column < value,
    FilterOperatorType.HAS_VALUE: lambda column, value: (
        column.is_not(None) if value else column.is_(None)
    ),
}

ORDER_BUILDER_BY_SORT_DIRECTION: dict[
    SortDirectionType, Callable[[QueryableAttribute[Any]], UnaryExpression[Any]]
] = {
    SortDirectionType.ASC: lambda column: column.asc(),
    SortDirectionType.DESC: lambda column: column.desc(),
}


class PageQueryUtils:
    """Builds the filtered, counted and paged queries of a list from its ListQueryConfig."""

    @staticmethod
    def build_filtered_query(
        all_records_query: Select[Any],
        list_query_config: ListQueryConfig,
        list_input: ListInput,
    ) -> Select[Any]:
        """Adds the list input's filters that are set and the search words to the query."""
        page_input = list_input.page_input
        filtered_query = all_records_query

        # Filters: an unset (None) field adds no condition
        for field_name, list_filter_config in list_query_config.filters.items():
            filter_value = getattr(list_input, field_name)
            if filter_value is None:
                continue
            build_condition = CONDITION_BUILDER_BY_OPERATOR[list_filter_config.operator]
            filtered_query = filtered_query.where(
                build_condition(list_filter_config.column, filter_value)
            )

        # Search: every word must match at least one search column
        search_words = (page_input.search or "").split()[:MAX_SEARCH_WORD_COUNT]
        if search_words:
            search_condition = and_(
                *[
                    or_(
                        *[
                            search_column.icontains(search_word, autoescape=True)
                            for search_column in list_query_config.search_columns
                        ]
                    )
                    for search_word in search_words
                ]
            )
            filtered_query = filtered_query.where(search_condition)

        return filtered_query

    @staticmethod
    def build_page_query(
        filtered_query: Select[Any],
        list_query_config: ListQueryConfig,
        list_input: ListInput,
    ) -> Select[Any]:
        """Adds the total of all filtered rows, orders by the sort column then the tiebreak
        column, and slices out one page."""
        page_input = list_input.page_input
        build_order = ORDER_BUILDER_BY_SORT_DIRECTION[page_input.sort_direction]
        sort_column = list_query_config.sort_columns[list_input.sort_by]
        offset = (page_input.page - 1) * page_input.page_size
        return (
            # The window runs before LIMIT and OFFSET, so each row carries the full total
            filtered_query.add_columns(func.count().over().label("total"))
            .order_by(
                build_order(sort_column).nulls_last(),
                build_order(list_query_config.tiebreak_column),
            )
            .limit(page_input.page_size)
            .offset(offset)
        )

    @staticmethod
    def build_count_query(filtered_query: Select[Any]) -> Select[Any]:
        """Counts the rows the filtered query matches, ignoring any ordering."""
        unordered_subquery = filtered_query.order_by(None).subquery()
        return select(func.count()).select_from(unordered_subquery)

    @staticmethod
    def build_page_info(page_input: PageInput, total: int) -> PageInfoResult:
        """Returns the requested page, its size and the total row count."""
        return PageInfoResult(page=page_input.page, page_size=page_input.page_size, total=total)
