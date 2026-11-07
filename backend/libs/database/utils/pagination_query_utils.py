from collections.abc import Callable
from typing import Any

from sqlalchemy import ColumnElement, Select, and_, func, or_, select
from sqlalchemy.orm import QueryableAttribute
from sqlalchemy.sql.elements import UnaryExpression

from libs.core.inputs import BasePageInput, PaginationInput
from libs.core.results import PaginationResult
from libs.core.types import FilterOperatorType, SortDirectionType
from libs.database.pagination_config import PaginationConfig

MAX_SEARCH_WORD_COUNT = 8
PAGE_TOTAL_LABEL = "total"

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


class PaginationQueryUtils:
    """Builds the filtered, counted and paged queries of a paged route from its PaginationConfig."""

    @staticmethod
    def build_filtered_query(
        all_records_query: Select[Any],
        pagination_config: PaginationConfig,
        page_input: BasePageInput,
    ) -> Select[Any]:
        """Adds the page input's filters that are set and the search words to the query."""
        pagination_input = page_input.pagination_input
        filtered_query = all_records_query

        # Filters: an unset (None) field adds no condition
        for field_name, pagination_filter_config in pagination_config.filters.items():
            filter_value = getattr(page_input, field_name)
            if filter_value is None:
                continue
            build_condition = CONDITION_BUILDER_BY_OPERATOR[pagination_filter_config.operator]
            filtered_query = filtered_query.where(
                build_condition(pagination_filter_config.column, filter_value)
            )

        # Search: every word must match at least one search column
        search_words = (pagination_input.search or "").split()[:MAX_SEARCH_WORD_COUNT]
        if search_words:
            search_condition = and_(
                *[
                    or_(
                        *[
                            search_column.icontains(search_word, autoescape=True)
                            for search_column in pagination_config.search_columns
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
        pagination_config: PaginationConfig,
        page_input: BasePageInput,
    ) -> Select[Any]:
        """Adds the total of all filtered rows, orders by the sort column then the tiebreak
        column, and slices out one page."""
        pagination_input = page_input.pagination_input
        build_order = ORDER_BUILDER_BY_SORT_DIRECTION[pagination_input.sort_direction]
        sort_column = pagination_config.sort_columns[page_input.sort_by]
        offset = (pagination_input.page - 1) * pagination_input.page_size
        return (
            # The window runs before LIMIT and OFFSET, so each row carries the full total
            filtered_query.add_columns(func.count().over().label(PAGE_TOTAL_LABEL))
            .order_by(
                build_order(sort_column).nulls_last(),
                build_order(pagination_config.tiebreak_column),
            )
            .limit(pagination_input.page_size)
            .offset(offset)
        )

    @staticmethod
    def build_count_query(filtered_query: Select[Any]) -> Select[Any]:
        """Counts the rows the filtered query matches, ignoring any ordering."""
        unordered_subquery = filtered_query.order_by(None).subquery()
        return select(func.count()).select_from(unordered_subquery)

    @staticmethod
    def build_pagination_result(pagination_input: PaginationInput, total: int) -> PaginationResult:
        """Returns the requested page, its size and the total row count."""
        return PaginationResult(
            page=pagination_input.page, page_size=pagination_input.page_size, total=total
        )
