from decimal import Decimal

from pydantic import BaseModel


class FindCreditBalanceResult(BaseModel):
    credit_balance_usd: Decimal
