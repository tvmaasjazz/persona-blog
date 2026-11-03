from decimal import ROUND_HALF_UP, Decimal

from libs.credits.constants import USD_QUANTUM


class CreditUtils:
    """Prices LLM costs for users and judges balances; static methods only."""

    @staticmethod
    def compute_charge_usd(cost_usd: Decimal, markup_multiplier: Decimal) -> Decimal:
        """Returns the user's price for a cost: the cost times the markup, rounded to the
        column's scale."""
        charge_usd = cost_usd * markup_multiplier
        return charge_usd.quantize(USD_QUANTUM, rounding=ROUND_HALF_UP)

    @staticmethod
    def is_balance_low(credit_balance_usd: Decimal, low_balance_threshold_usd: Decimal) -> bool:
        """Returns whether the balance is strictly below the threshold."""
        return credit_balance_usd < low_balance_threshold_usd
