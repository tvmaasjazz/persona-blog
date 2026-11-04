from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class CreditSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    markup_multiplier: Decimal = Decimal("1")
    minimum_run_balance_usd: Decimal = Decimal("0.10")
    low_balance_threshold_usd: Decimal = Decimal("0.50")
