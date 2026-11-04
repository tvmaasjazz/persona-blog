from decimal import Decimal

from pydantic import BaseModel


class GrantCreditsInput(BaseModel):
    user_id: int
    amount_usd: Decimal
    note: str | None


class ChargeCreditsInput(BaseModel):
    user_id: int
    amount_usd: Decimal
    generate_text_run_id: int
    generate_text_step_id: int
