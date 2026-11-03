from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.auth.results import AuthUser
from libs.core.exceptions import NotFoundException
from libs.credits.exceptions import CreditBalanceInsufficientException
from libs.database.orm.user import UserOrm


class CreditValidationService:
    """Holds the credit checks a validation guard calls."""

    def __init__(self, db_session: AsyncSession) -> None:
        self._db_session = db_session

    async def validate_balance_covers_run(
        self, auth_user: AuthUser, minimum_run_balance_usd: Decimal
    ) -> None:
        """Passes when the user's balance reaches the minimum to start a run;
        CreditBalanceInsufficientException otherwise."""
        credit_balance_query = select(UserOrm.credit_balance_usd).where(UserOrm.id == auth_user.id)
        credit_balance_query_result = await self._db_session.execute(credit_balance_query)
        credit_balance_usd = credit_balance_query_result.scalar_one_or_none()

        if credit_balance_usd is None:
            raise NotFoundException("User not found")
        if credit_balance_usd < minimum_run_balance_usd:
            raise CreditBalanceInsufficientException("Credit balance is too low to start a run")
