from enum import StrEnum

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from libs.core.inputs import ListInput, PageInput
from libs.core.results import PageInfoResult
from libs.core.types import SortDirectionType
from libs.database.list_query_config import ListQueryConfig
from libs.database.orm import ContentItemOrm, PersonaOrm, UserOrm
from libs.database.results import FindPageResult
from libs.database.services import PageQueryService
from tests.factories.content_items import insert_content_item_row
from tests.factories.core import build_page_input
from tests.factories.personas import insert_persona_row
from tests.factories.users import find_system_user_row, insert_user_row


class UserSortType(StrEnum):
    EMAIL = "EMAIL"


class ContentItemSortType(StrEnum):
    CREATED = "CREATED"


class ContentItemListInput(ListInput):
    sort_by: ContentItemSortType = ContentItemSortType.CREATED


class UserListInput(ListInput):
    sort_by: UserSortType = UserSortType.EMAIL


USER_LIST_CONFIG = ListQueryConfig(
    search_columns=(UserOrm.email,),
    sort_columns={UserSortType.EMAIL: UserOrm.email},
    filters={},
    tiebreak_column=UserOrm.id,
)

CONTENT_ITEM_LIST_CONFIG = ListQueryConfig(
    search_columns=(PersonaOrm.name,),
    sort_columns={ContentItemSortType.CREATED: ContentItemOrm.id},
    filters={},
    tiebreak_column=ContentItemOrm.id,
)


def _build_user_list_input(page_input: PageInput) -> UserListInput:
    return UserListInput(page_input=page_input, sort_by=UserSortType.EMAIL)


def _build_user_base_query() -> Select[tuple[UserOrm]]:
    return select(UserOrm).where(UserOrm.email.like("find-page-%"))


async def _insert_find_page_users(db_session: AsyncSession) -> list[UserOrm]:
    user_records = [
        await insert_user_row(db_session, email=f"find-page-{letter}@example.com")
        for letter in "abcde"
    ]
    await insert_user_row(db_session, email="other@example.com")
    return user_records


async def test_find_page_returns_the_page_records_in_order_with_page_info(
    db_session: AsyncSession,
) -> None:
    user_records = await _insert_find_page_users(db_session)
    page_query_service = PageQueryService(db_session=db_session)
    user_list_input = _build_user_list_input(
        build_page_input(page=2, page_size=2, sort_direction=SortDirectionType.ASC)
    )

    find_page_result = await page_query_service.find_page(
        _build_user_base_query(), USER_LIST_CONFIG, user_list_input
    )

    assert find_page_result == FindPageResult(
        records=[user_records[2], user_records[3]],
        page_info=PageInfoResult(page=2, page_size=2, total=5),
    )


async def test_find_page_empty_first_page_returns_total_zero(db_session: AsyncSession) -> None:
    page_query_service = PageQueryService(db_session=db_session)
    user_list_input = _build_user_list_input(build_page_input(page=1, page_size=2))

    find_page_result = await page_query_service.find_page(
        _build_user_base_query(), USER_LIST_CONFIG, user_list_input
    )

    assert find_page_result == FindPageResult(
        records=[], page_info=PageInfoResult(page=1, page_size=2, total=0)
    )


async def test_find_page_empty_page_past_the_end_returns_the_full_total(
    db_session: AsyncSession,
) -> None:
    await _insert_find_page_users(db_session)
    page_query_service = PageQueryService(db_session=db_session)
    user_list_input = _build_user_list_input(build_page_input(page=9, page_size=2))

    find_page_result = await page_query_service.find_page(
        _build_user_base_query(), USER_LIST_CONFIG, user_list_input
    )

    assert find_page_result == FindPageResult(
        records=[], page_info=PageInfoResult(page=9, page_size=2, total=5)
    )


async def test_find_page_search_counts_only_matching_rows(db_session: AsyncSession) -> None:
    await _insert_find_page_users(db_session)
    page_query_service = PageQueryService(db_session=db_session)
    user_list_input = _build_user_list_input(
        build_page_input(page=1, page_size=1, search="find-page-b")
    )

    find_page_result = await page_query_service.find_page(
        _build_user_base_query(), USER_LIST_CONFIG, user_list_input
    )

    assert [user_record.email for user_record in find_page_result.records] == [
        "find-page-b@example.com"
    ]
    assert find_page_result.page_info == PageInfoResult(page=1, page_size=1, total=1)


async def test_find_page_load_options_load_the_relationship_on_the_records(
    db_session: AsyncSession,
) -> None:
    system_user_record = await find_system_user_row(db_session)
    persona_record = await insert_persona_row(
        db_session, created_by_id=system_user_record.id, name="Slow Mornings Sam"
    )
    await insert_content_item_row(
        db_session, created_by_id=system_user_record.id, persona_id=persona_record.id
    )
    # A fresh load, so the relationship can only come from the loader option
    db_session.expunge_all()
    page_query_service = PageQueryService(db_session=db_session)
    all_records_query = (
        select(ContentItemOrm)
        .join(ContentItemOrm.persona)
        .where(PersonaOrm.name == "Slow Mornings Sam")
    )
    content_item_list_input = ContentItemListInput(
        page_input=build_page_input(), sort_by=ContentItemSortType.CREATED
    )

    find_page_result = await page_query_service.find_page(
        all_records_query,
        CONTENT_ITEM_LIST_CONFIG,
        content_item_list_input,
        load_options=(contains_eager(ContentItemOrm.persona),),
    )

    assert [
        content_item_record.persona.name for content_item_record in find_page_result.records
    ] == ["Slow Mornings Sam"]
