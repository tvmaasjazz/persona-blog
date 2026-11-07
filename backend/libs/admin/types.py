from enum import StrEnum


class AdminUserSortType(StrEnum):
    CREATED_AT = "CREATED_AT"
    EMAIL = "EMAIL"
    LAST_ACTIVITY_AT = "LAST_ACTIVITY_AT"


class AdminInviteSortType(StrEnum):
    CREATED_AT = "CREATED_AT"
    NAME = "NAME"
    EXPIRES_AT = "EXPIRES_AT"


class AdminCreditLedgerSortType(StrEnum):
    CREATED_AT = "CREATED_AT"
