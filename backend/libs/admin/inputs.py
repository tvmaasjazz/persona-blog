from decimal import Decimal

from pydantic import BaseModel


class GrantUserCreditsInput(BaseModel):
    amount_usd: Decimal
    note: str
