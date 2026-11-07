from collections.abc import Sequence
from typing import Any

from sqlalchemy import Row, Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.interfaces import ExecutableOption

from libs.core.inputs import BasePageInput
from libs.core.results import PaginationResult
from libs.database.pagination_config import PaginationConfig
from libs.database.results import FindPageResult
from libs.database.utils import PaginationQueryUtils
from libs.database.utils.pagination_query_utils import PAGE_TOTAL_LABEL


class PaginationService:
    """Runs one page of a query and finds its total."""

    def __init__(self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    async def find_page(
        self,
        all_records_query: Select[Any],
        pagination_config: PaginationConfig,
        page_input: BasePageInput,
        load_options: Sequence[ExecutableOption] = (),
    ) -> FindPageResult:
        """Runs one page of a query that selects one Orm entity, returning the entities, with
        loader options on the page only."""
        page_rows, pagination = await self._find_page_rows(
            all_records_query, pagination_config, page_input, load_options
        )
        return FindPageResult(
            records=[page_row[0] for page_row in page_rows], pagination=pagination
        )

    async def find_mapping_page(
        self,
        all_records_query: Select[Any],
        pagination_config: PaginationConfig,
        page_input: BasePageInput,
    ) -> FindPageResult:
        """Runs one page of a query that selects columns, returning each row as a mapping of
        its labels."""
        page_rows, pagination = await self._find_page_rows(
            all_records_query, pagination_config, page_input
        )
        return FindPageResult(
            records=[
                {
                    label: value
                    for label, value in page_row._mapping.items()
                    if label != PAGE_TOTAL_LABEL
                }
                for page_row in page_rows
            ],
            pagination=pagination,
        )

    async def _find_page_rows(
        self,
        all_records_query: Select[Any],
        pagination_config: PaginationConfig,
        page_input: BasePageInput,
        load_options: Sequence[ExecutableOption] = (),
    ) -> tuple[Sequence[Row[Any]], PaginationResult]:
        """Runs one page of the query and finds its total."""
        pagination_input = page_input.pagination_input

        # Filter and search the records, then slice out the page with a window total
        filtered_query = PaginationQueryUtils.build_filtered_query(
            all_records_query, pagination_config, page_input
        )
        page_query = PaginationQueryUtils.build_page_query(
            filtered_query, pagination_config, page_input
        ).options(*load_options)
        page_query_result = await self._db_session.execute(page_query)
        page_rows = page_query_result.all()

        # Every row carries the total; an empty page past the first needs a count to find it
        total = 0
        if page_rows:
            total = page_rows[0].total
        elif pagination_input.page > 1:
            count_query = PaginationQueryUtils.build_count_query(filtered_query)
            count_query_result = await self._db_session.execute(count_query)
            total = count_query_result.scalar_one()

        return page_rows, PaginationQueryUtils.build_pagination_result(pagination_input, total)
