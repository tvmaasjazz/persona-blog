from collections.abc import Sequence
from typing import Any

from sqlalchemy import Select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm.interfaces import ExecutableOption

from libs.core.inputs import ListInput
from libs.database.list_query_config import ListQueryConfig
from libs.database.results import FindPageResult
from libs.database.utils import PageQueryUtils


class PageQueryService:
    """Runs one page of a list and finds its total."""

    def __init__(self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    async def find_page(
        self,
        all_records_query: Select[Any],
        list_query_config: ListQueryConfig,
        list_input: ListInput,
        load_options: Sequence[ExecutableOption] = (),
    ) -> FindPageResult:
        """Runs one page of a list and finds its total, with loader options on the page only."""
        page_input = list_input.page_input

        # Filter and search the records, then slice out the page with a window total
        filtered_query = PageQueryUtils.build_filtered_query(
            all_records_query, list_query_config, list_input
        )
        page_query = PageQueryUtils.build_page_query(
            filtered_query, list_query_config, list_input
        ).options(*load_options)
        page_query_result = await self._db_session.execute(page_query)
        page_rows = page_query_result.all()

        # Every row carries the total; an empty page past the first needs a count to find it
        records = [page_row[0] for page_row in page_rows]
        total = 0
        if page_rows:
            total = page_rows[0].total
        elif page_input.page > 1:
            count_query = PageQueryUtils.build_count_query(filtered_query)
            count_query_result = await self._db_session.execute(count_query)
            total = count_query_result.scalar_one()

        return FindPageResult(
            records=records,
            page_info=PageQueryUtils.build_page_info(page_input, total),
        )
