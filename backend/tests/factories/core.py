from libs.core.inputs import PageInput
from libs.core.types import SortDirectionType


def build_page_input(
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    sort_direction: SortDirectionType = SortDirectionType.DESC,
) -> PageInput:
    return PageInput(
        page=page,
        page_size=page_size,
        search=search,
        sort_direction=sort_direction,
    )
