from decimal import Decimal

from pydantic import BaseModel


class AdminGrantUserCreditsInput(BaseModel):
    amount_usd: Decimal
    note: str
