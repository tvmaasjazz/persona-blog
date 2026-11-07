from enum import StrEnum

from sqlalchemy import Select, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import contains_eager

from libs.core.inputs import BasePageInput, PaginationInput
from libs.core.results import PaginationResult
from libs.core.types import SortDirectionType
from libs.database.orm import ContentItemOrm, PersonaOrm, UserOrm
from libs.database.pagination_config import PaginationConfig
from libs.database.results import FindPageResult
from libs.database.services import PaginationService
from tests.factories.content_items import insert_content_item_row
from tests.factories.core import build_pagination_input
from tests.factories.personas import insert_persona_row
from tests.factories.users import find_system_user_row, insert_user_row


class UserSortType(StrEnum):
    EMAIL = "EMAIL"


class ContentItemSortType(StrEnum):
    CREATED = "CREATED"


class ContentItemPageInput(BasePageInput):
    sort_by: ContentItemSortType = ContentItemSortType.CREATED


class UserPageInput(BasePageInput):
    sort_by: UserSortType = UserSortType.EMAIL


USER_PAGINATION_CONFIG = PaginationConfig(
    search_columns=(UserOrm.email,),
    sort_columns={UserSortType.EMAIL: UserOrm.email},
    filters={},
    tiebreak_column=UserOrm.id,
)

CONTENT_ITEM_PAGINATION_CONFIG = PaginationConfig(
    search_columns=(PersonaOrm.name,),
    sort_columns={ContentItemSortType.CREATED: ContentItemOrm.id},
    filters={},
    tiebreak_column=ContentItemOrm.id,
)


def _build_user_page_input(pagination_input: PaginationInput) -> UserPageInput:
    return UserPageInput(pagination_input=pagination_input, sort_by=UserSortType.EMAIL)


def _build_user_base_query() -> Select[tuple[UserOrm]]:
    return select(UserOrm).where(UserOrm.email.like("find-page-%"))


async def _insert_find_page_users(db_session: AsyncSession) -> list[UserOrm]:
    user_records = [
        await insert_user_row(db_session, email=f"find-page-{letter}@example.com")
        for letter in "abcde"
    ]
    await insert_user_row(db_session, email="other@example.com")
    return user_records


async def test_find_page_returns_the_page_records_in_order_with_pagination(
    db_session: AsyncSession,
) -> None:
    user_records = await _insert_find_page_users(db_session)
    pagination_service = PaginationService(db_session=db_session)
    user_page_input = _build_user_page_input(
        build_pagination_input(page=2, page_size=2, sort_direction=SortDirectionType.ASC)
    )

    find_page_result = await pagination_service.find_page(
        _build_user_base_query(), USER_PAGINATION_CONFIG, user_page_input
    )

    assert find_page_result == FindPageResult(
        records=[user_records[2], user_records[3]],
        pagination=PaginationResult(page=2, page_size=2, total=5),
    )


async def test_find_page_empty_first_page_returns_total_zero(db_session: AsyncSession) -> None:
    pagination_service = PaginationService(db_session=db_session)
    user_page_input = _build_user_page_input(build_pagination_input(page=1, page_size=2))

    find_page_result = await pagination_service.find_page(
        _build_user_base_query(), USER_PAGINATION_CONFIG, user_page_input
    )

    assert find_page_result == FindPageResult(
        records=[], pagination=PaginationResult(page=1, page_size=2, total=0)
    )


async def test_find_page_empty_page_past_the_end_returns_the_full_total(
    db_session: AsyncSession,
) -> None:
    await _insert_find_page_users(db_session)
    pagination_service = PaginationService(db_session=db_session)
    user_page_input = _build_user_page_input(build_pagination_input(page=9, page_size=2))

    find_page_result = await pagination_service.find_page(
        _build_user_base_query(), USER_PAGINATION_CONFIG, user_page_input
    )

    assert find_page_result == FindPageResult(
        records=[], pagination=PaginationResult(page=9, page_size=2, total=5)
    )


async def test_find_page_search_counts_only_matching_rows(db_session: AsyncSession) -> None:
    await _insert_find_page_users(db_session)
    pagination_service = PaginationService(db_session=db_session)
    user_page_input = _build_user_page_input(
        build_pagination_input(page=1, page_size=1, search="find-page-b")
    )

    find_page_result = await pagination_service.find_page(
        _build_user_base_query(), USER_PAGINATION_CONFIG, user_page_input
    )

    assert [user_record.email for user_record in find_page_result.records] == [
        "find-page-b@example.com"
    ]
    assert find_page_result.pagination == PaginationResult(page=1, page_size=1, total=1)


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
    pagination_service = PaginationService(db_session=db_session)
    all_records_query = (
        select(ContentItemOrm)
        .join(ContentItemOrm.persona)
        .where(PersonaOrm.name == "Slow Mornings Sam")
    )
    content_item_page_input = ContentItemPageInput(
        pagination_input=build_pagination_input(), sort_by=ContentItemSortType.CREATED
    )

    find_page_result = await pagination_service.find_page(
        all_records_query,
        CONTENT_ITEM_PAGINATION_CONFIG,
        content_item_page_input,
        load_options=(contains_eager(ContentItemOrm.persona),),
    )

    assert [
        content_item_record.persona.name for content_item_record in find_page_result.records
    ] == ["Slow Mornings Sam"]


async def test_find_mapping_page_returns_the_page_rows_as_label_dicts_without_the_total(
    db_session: AsyncSession,
) -> None:
    await _insert_find_page_users(db_session)
    pagination_service = PaginationService(db_session=db_session)
    user_page_input = _build_user_page_input(
        build_pagination_input(page=2, page_size=2, sort_direction=SortDirectionType.ASC)
    )
    all_records_query = select(
        UserOrm.email.label("user_email"), UserOrm.is_active.label("user_is_active")
    ).where(UserOrm.email.like("find-page-%"))

    find_mapping_page_result = await pagination_service.find_mapping_page(
        all_records_query, USER_PAGINATION_CONFIG, user_page_input
    )

    assert find_mapping_page_result == FindPageResult(
        records=[
            {"user_email": "find-page-c@example.com", "user_is_active": True},
            {"user_email": "find-page-d@example.com", "user_is_active": True},
        ],
        pagination=PaginationResult(page=2, page_size=2, total=5),
    )


async def test_find_mapping_page_sorts_by_a_column_that_is_not_selected(
    db_session: AsyncSession,
) -> None:
    await _insert_find_page_users(db_session)
    pagination_service = PaginationService(db_session=db_session)
    user_page_input = _build_user_page_input(
        build_pagination_input(sort_direction=SortDirectionType.DESC)
    )
    all_records_query = select(UserOrm.is_active.label("user_is_active")).where(
        UserOrm.email.like("find-page-%")
    )

    find_mapping_page_result = await pagination_service.find_mapping_page(
        all_records_query, USER_PAGINATION_CONFIG, user_page_input
    )

    assert find_mapping_page_result == FindPageResult(
        records=[{"user_is_active": True}] * 5,
        pagination=PaginationResult(page=1, page_size=20, total=5),
    )


async def test_find_mapping_page_empty_first_page_returns_total_zero(
    db_session: AsyncSession,
) -> None:
    pagination_service = PaginationService(db_session=db_session)
    user_page_input = _build_user_page_input(build_pagination_input(page=1, page_size=2))
    all_records_query = select(UserOrm.email.label("user_email")).where(
        UserOrm.email.like("find-page-%")
    )

    find_mapping_page_result = await pagination_service.find_mapping_page(
        all_records_query, USER_PAGINATION_CONFIG, user_page_input
    )

    assert find_mapping_page_result == FindPageResult(
        records=[], pagination=PaginationResult(page=1, page_size=2, total=0)
    )


async def test_find_mapping_page_empty_page_past_the_end_returns_the_full_total(
    db_session: AsyncSession,
) -> None:
    await _insert_find_page_users(db_session)
    pagination_service = PaginationService(db_session=db_session)
    user_page_input = _build_user_page_input(build_pagination_input(page=9, page_size=2))
    all_records_query = select(UserOrm.email.label("user_email")).where(
        UserOrm.email.like("find-page-%")
    )

    find_mapping_page_result = await pagination_service.find_mapping_page(
        all_records_query, USER_PAGINATION_CONFIG, user_page_input
    )

    assert find_mapping_page_result == FindPageResult(
        records=[], pagination=PaginationResult(page=9, page_size=2, total=5)
    )


async def test_find_mapping_page_search_counts_only_matching_rows(
    db_session: AsyncSession,
) -> None:
    await _insert_find_page_users(db_session)
    pagination_service = PaginationService(db_session=db_session)
    user_page_input = _build_user_page_input(
        build_pagination_input(page=1, page_size=1, search="find-page-b")
    )
    all_records_query = select(UserOrm.email.label("user_email")).where(
        UserOrm.email.like("find-page-%")
    )

    find_mapping_page_result = await pagination_service.find_mapping_page(
        all_records_query, USER_PAGINATION_CONFIG, user_page_input
    )

    assert find_mapping_page_result == FindPageResult(
        records=[{"user_email": "find-page-b@example.com"}],
        pagination=PaginationResult(page=1, page_size=1, total=1),
    )
