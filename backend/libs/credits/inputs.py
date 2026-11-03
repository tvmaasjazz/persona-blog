from decimal import Decimal

from pydantic import BaseModel


class GrantCreditsInput(BaseModel):
    user_id: int
    amount_usd: Decimal
    note: str | None
