from libs.admin.inputs import (
    AdminFindInvitePageInput,
    AdminFindUserCreditLedgerPageInput,
    AdminFindUserPageInput,
)
from libs.admin.types import AdminCreditLedgerSortType, AdminInviteSortType, AdminUserSortType
from libs.core.types import SortDirectionType
from tests.factories.core import build_pagination_input


def build_admin_find_user_page_input(
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    sort_by: AdminUserSortType = AdminUserSortType.CREATED_AT,
    sort_direction: SortDirectionType = SortDirectionType.DESC,
) -> AdminFindUserPageInput:
    return AdminFindUserPageInput(
        pagination_input=build_pagination_input(
            page=page, page_size=page_size, search=search, sort_direction=sort_direction
        ),
        sort_by=sort_by,
    )


def build_admin_find_invite_page_input(
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    sort_by: AdminInviteSortType = AdminInviteSortType.CREATED_AT,
    sort_direction: SortDirectionType = SortDirectionType.DESC,
) -> AdminFindInvitePageInput:
    return AdminFindInvitePageInput(
        pagination_input=build_pagination_input(
            page=page, page_size=page_size, search=search, sort_direction=sort_direction
        ),
        sort_by=sort_by,
    )


def build_admin_find_user_credit_ledger_page_input(
    *,
    page: int = 1,
    page_size: int = 20,
    search: str | None = None,
    sort_by: AdminCreditLedgerSortType = AdminCreditLedgerSortType.CREATED_AT,
    sort_direction: SortDirectionType = SortDirectionType.DESC,
) -> AdminFindUserCreditLedgerPageInput:
    return AdminFindUserCreditLedgerPageInput(
        pagination_input=build_pagination_input(
            page=page, page_size=page_size, search=search, sort_direction=sort_direction
        ),
        sort_by=sort_by,
    )
