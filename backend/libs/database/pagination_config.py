from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from sqlalchemy.orm import QueryableAttribute

from libs.core.inputs import BasePageInput
from libs.core.types import FilterOperatorType

# The page input fields every paged route has; the rest are its filters
PAGE_INPUT_BASE_FIELD_NAMES = frozenset(BasePageInput.model_fields)


@dataclass(frozen=True)
class PaginationFilterConfig:
    """One filterable column and the operator its page input value is compared with."""

    column: QueryableAttribute[Any]
    operator: FilterOperatorType


@dataclass(frozen=True)
class PaginationConfig:
    """The columns a paged route searches, sorts and filters by, for its page input class;
    filters are keyed by the page input's field name."""

    page_input_class: type[BasePageInput]
    search_columns: tuple[QueryableAttribute[Any], ...]
    sort_columns: Mapping[StrEnum, QueryableAttribute[Any]]
    filters: Mapping[str, PaginationFilterConfig]
    tiebreak_column: QueryableAttribute[Any]

    def __post_init__(self) -> None:
        """Raises ValueError, when the config is built at import, unless it sorts by every
        value of the input's sort type and filters by exactly the input's filter fields."""
        input_class_name = self.page_input_class.__name__

        # Every sort value has a column, and every column is keyed by a sort value
        sort_type = self.page_input_class.model_fields["sort_by"].annotation
        is_sort_type_enum = isinstance(sort_type, type) and issubclass(sort_type, StrEnum)
        if not is_sort_type_enum or sort_type is StrEnum:
            raise ValueError(f"{input_class_name}.sort_by must be typed as a StrEnum")
        if set(self.sort_columns) != set(sort_type):
            raise ValueError(
                f"The sort columns for {input_class_name} must be keyed by exactly the values "
                f"of {sort_type.__name__}"
            )

        # Every filter field of the input has a filter, and every filter is a field
        filter_field_names = set(self.page_input_class.model_fields) - PAGE_INPUT_BASE_FIELD_NAMES
        if set(self.filters) != filter_field_names:
            raise ValueError(
                f"The filters for {input_class_name} must be keyed by exactly its filter "
                f"fields: {sorted(filter_field_names)}"
            )
