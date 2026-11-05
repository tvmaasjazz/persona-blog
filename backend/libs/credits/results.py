from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel


class FindCreditBalanceResult(BaseModel):
    credit_balance_usd: Decimal


class RefundChargesResult(BaseModel):
    refund_usd: Decimal


class GrantCreditsResult(BaseModel):
    identity: UUID
