from enum import StrEnum


class CreditLedgerEntryType(StrEnum):
    """What a credit ledger row does to a balance."""

    GRANT = "GRANT"
    CHARGE = "CHARGE"
    REFUND = "REFUND"
    ADJUSTMENT = "ADJUSTMENT"
