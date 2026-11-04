from enum import StrEnum


class CreditLedgerEntryType(StrEnum):
    GRANT = "GRANT"
    CHARGE = "CHARGE"
    REFUND = "REFUND"
    ADJUSTMENT = "ADJUSTMENT"
