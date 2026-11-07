from decimal import Decimal

from libs.admin.inputs import (
    AdminFindInvitePageInput,
    AdminFindUserCreditLedgerPageInput,
    AdminFindUserPageInput,
)
from libs.admin.types import AdminCreditLedgerSortType, AdminInviteSortType, AdminUserSortType
from libs.database.orm import CreditLedgerOrm, InviteOrm, UserOrm
from libs.database.pagination_config import PaginationConfig

# The most one grant may give, so a typo like 1000 for 10 is refused
MAX_CREDIT_GRANT_USD = Decimal(100)

ADMIN_USER_PAGINATION_CONFIG = PaginationConfig(
    page_input_class=AdminFindUserPageInput,
    search_columns=(UserOrm.email, UserOrm.display_name),
    sort_columns={
        AdminUserSortType.CREATED_AT: UserOrm.created_at,
        AdminUserSortType.EMAIL: UserOrm.email,
        AdminUserSortType.LAST_ACTIVITY_AT: UserOrm.last_activity_at,
    },
    filters={},
    tiebreak_column=UserOrm.id,
)

ADMIN_INVITE_PAGINATION_CONFIG = PaginationConfig(
    page_input_class=AdminFindInvitePageInput,
    search_columns=(InviteOrm.name,),
    sort_columns={
        AdminInviteSortType.CREATED_AT: InviteOrm.created_at,
        AdminInviteSortType.NAME: InviteOrm.name,
        AdminInviteSortType.EXPIRES_AT: InviteOrm.expires_at,
    },
    filters={},
    tiebreak_column=InviteOrm.id,
)

ADMIN_CREDIT_LEDGER_PAGINATION_CONFIG = PaginationConfig(
    page_input_class=AdminFindUserCreditLedgerPageInput,
    search_columns=(CreditLedgerOrm.note,),
    sort_columns={AdminCreditLedgerSortType.CREATED_AT: CreditLedgerOrm.created_at},
    filters={},
    tiebreak_column=CreditLedgerOrm.id,
)
