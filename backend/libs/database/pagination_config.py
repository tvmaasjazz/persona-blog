from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from sqlalchemy.orm import QueryableAttribute

from libs.core.types import FilterOperatorType


@dataclass(frozen=True)
class PaginationFilterConfig:
    """One filterable column and the operator its page input value is compared with."""

    column: QueryableAttribute[Any]
    operator: FilterOperatorType


@dataclass(frozen=True)
class PaginationConfig:
    """The columns a paged route searches, sorts and filters by; filters are keyed by the page
    input's field name."""

    search_columns: tuple[QueryableAttribute[Any], ...]
    sort_columns: Mapping[StrEnum, QueryableAttribute[Any]]
    filters: Mapping[str, PaginationFilterConfig]
    tiebreak_column: QueryableAttribute[Any]
