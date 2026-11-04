from decimal import Decimal

import pytest

from libs.credits.utils import CreditUtils


@pytest.mark.parametrize(
    ("cost_usd", "markup_multiplier", "expected_charge_usd"),
    [
        pytest.param(Decimal("0.01"), Decimal("1"), Decimal("0.0100000000"), id="no_markup"),
        pytest.param(Decimal("0.01"), Decimal("2"), Decimal("0.0200000000"), id="doubled"),
        pytest.param(Decimal("0"), Decimal("3"), Decimal("0"), id="free_cost"),
        pytest.param(
            Decimal("0.0123456789"),
            Decimal("1.5"),
            Decimal("0.0185185184"),
            id="rounded_to_ten_decimal_places",
        ),
    ],
)
def test_compute_charge_usd_applies_markup_and_rounds_to_ten_decimal_places(
    cost_usd: Decimal, markup_multiplier: Decimal, expected_charge_usd: Decimal
) -> None:
    charge_usd = CreditUtils.compute_charge_usd(cost_usd, markup_multiplier)

    assert charge_usd == expected_charge_usd
    assert charge_usd.as_tuple().exponent == -10


@pytest.mark.parametrize(
    ("credit_balance_usd", "low_balance_threshold_usd", "expected_is_balance_low"),
    [
        pytest.param(Decimal("0.49"), Decimal("0.50"), True, id="below"),
        pytest.param(Decimal("0.50"), Decimal("0.50"), False, id="at"),
        pytest.param(Decimal("0.51"), Decimal("0.50"), False, id="above"),
        pytest.param(Decimal("-0.01"), Decimal("0"), True, id="negative_below_zero_threshold"),
    ],
)
def test_is_balance_low_is_true_only_strictly_below_threshold(
    credit_balance_usd: Decimal, low_balance_threshold_usd: Decimal, expected_is_balance_low: bool
) -> None:
    is_balance_low = CreditUtils.is_balance_low(credit_balance_usd, low_balance_threshold_usd)

    assert is_balance_low is expected_is_balance_low
