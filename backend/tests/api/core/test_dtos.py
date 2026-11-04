from decimal import Decimal

import pytest
from pydantic import BaseModel

from apps.api.core.dtos import UsdDecimal


class UsdAmountResponseDto(BaseModel):
    amount_usd: UsdDecimal


@pytest.mark.parametrize(
    ("amount_usd", "expected_amount_usd"),
    [
        pytest.param(Decimal("0E-10"), "0.0000000000", id="rounded_zero"),
        pytest.param(Decimal("5.0000000000"), "5.0000000000", id="whole_dollars"),
        pytest.param(Decimal("0.0000000001"), "0.0000000001", id="smallest_step"),
        pytest.param(Decimal("1E-7"), "0.0000001", id="exponent_form"),
        pytest.param(Decimal("-0.0000055500"), "-0.0000055500", id="negative"),
        pytest.param(Decimal("999999.9999999999"), "999999.9999999999", id="column_maximum"),
    ],
)
def test_usd_decimal_writes_plain_digits_that_parse_back_to_the_same_value(
    amount_usd: Decimal, expected_amount_usd: str
) -> None:
    usd_amount_response_dto = UsdAmountResponseDto(amount_usd=amount_usd)

    response_body = usd_amount_response_dto.model_dump(mode="json")

    assert response_body["amount_usd"] == expected_amount_usd
    assert Decimal(response_body["amount_usd"]) == amount_usd


def test_usd_decimal_keeps_a_decimal_outside_json() -> None:
    usd_amount_response_dto = UsdAmountResponseDto(amount_usd=Decimal("0.30"))

    response_values = usd_amount_response_dto.model_dump()

    assert response_values["amount_usd"] == Decimal("0.30")
