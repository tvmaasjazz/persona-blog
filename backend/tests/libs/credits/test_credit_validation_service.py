from decimal import Decimal

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from libs.core.exceptions import NotFoundException
from libs.credits.exceptions import CreditBalanceInsufficientException
from libs.credits.services import CreditValidationService
from tests.factories.auth import build_auth_user
from tests.factories.users import insert_user_row


@pytest.mark.parametrize(
    "credit_balance_usd",
    [
        pytest.param(Decimal("0.10"), id="at_minimum"),
        pytest.param(Decimal("0.11"), id="above_minimum"),
    ],
)
async def test_validate_balance_covers_run_at_or_above_minimum_passes(
    db_session: AsyncSession, credit_balance_usd: Decimal
) -> None:
    user_record = await insert_user_row(db_session, credit_balance_usd=credit_balance_usd)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    credit_validation_service = CreditValidationService(db_session=db_session)

    await credit_validation_service.validate_balance_covers_run(auth_user, Decimal("0.10"))


@pytest.mark.parametrize(
    "credit_balance_usd",
    [
        pytest.param(Decimal("0.0999999999"), id="just_below_minimum"),
        pytest.param(Decimal("0"), id="zero"),
        pytest.param(Decimal("-1.00"), id="negative"),
    ],
)
async def test_validate_balance_covers_run_below_minimum_raises_balance_insufficient_exception(
    db_session: AsyncSession, credit_balance_usd: Decimal
) -> None:
    user_record = await insert_user_row(db_session, credit_balance_usd=credit_balance_usd)
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    credit_validation_service = CreditValidationService(db_session=db_session)

    with pytest.raises(CreditBalanceInsufficientException):
        await credit_validation_service.validate_balance_covers_run(auth_user, Decimal("0.10"))


async def test_validate_balance_covers_run_ignores_another_users_balance(
    db_session: AsyncSession,
) -> None:
    user_record = await insert_user_row(db_session, credit_balance_usd=Decimal("0"))
    await insert_user_row(db_session, credit_balance_usd=Decimal("50.00"))
    auth_user = build_auth_user(user_id=user_record.id, user_identity=user_record.identity)
    credit_validation_service = CreditValidationService(db_session=db_session)

    with pytest.raises(CreditBalanceInsufficientException):
        await credit_validation_service.validate_balance_covers_run(auth_user, Decimal("0.10"))


async def test_validate_balance_covers_run_unknown_user_raises_not_found_exception(
    db_session: AsyncSession,
) -> None:
    auth_user = build_auth_user(user_id=999999)
    credit_validation_service = CreditValidationService(db_session=db_session)

    with pytest.raises(NotFoundException):
        await credit_validation_service.validate_balance_covers_run(auth_user, Decimal("0.10"))
