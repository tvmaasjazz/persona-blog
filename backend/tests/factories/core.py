from libs.core.inputs import PaginationInput
from libs.core.types import SortDirectionType


def build_pagination_input(
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    sort_direction: SortDirectionType = SortDirectionType.DESC,
) -> PaginationInput:
    return PaginationInput(
        page=page,
        page_size=page_size,
        search=search,
        sort_direction=sort_direction,
    )
