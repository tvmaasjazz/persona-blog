"""Grants a user credits and makes a reader a creator, until the admin panel does it.

Run from backend/ against the database in .env:

    uv run python -m scripts.grant_credits --email someone@example.com --amount 1.00 --note "Beta"
"""

import argparse
import asyncio
import sys
from decimal import Decimal, InvalidOperation

from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from apps.api.core.config import AppSettings
from libs.admin.inputs import AdminGrantUserCreditsInput
from libs.admin.services import AdminCreditService
from libs.auth.results import AuthUser
from libs.credits.services import CreditLedgerService
from libs.database.orm import UserOrm
from libs.database.session import create_db_session_factory
from libs.permissions.types import RoleType


def _parse_arguments() -> argparse.Namespace:
    argument_parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argument_parser.add_argument("--email", required=True, help="the user's sign-in email")
    argument_parser.add_argument("--amount", required=True, help="USD to grant, e.g. 1.00")
    argument_parser.add_argument("--note", required=True, help="why, kept on the ledger row")
    return argument_parser.parse_args()


def _parse_amount_usd(amount_text: str) -> Decimal:
    try:
        amount_usd = Decimal(amount_text)
    except InvalidOperation:
        raise SystemExit(f"--amount must be a number, got {amount_text!r}") from None
    if amount_usd <= 0:
        raise SystemExit("--amount must be above 0")
    return amount_usd


async def _grant_credits(email: str, amount_usd: Decimal, note: str) -> None:
    app_settings = AppSettings()
    db_engine = create_async_engine(app_settings.database_url)
    db_session_factory = create_db_session_factory(db_engine)
    try:
        async with db_session_factory() as db_session, db_session.begin():
            # Find the user and the system user the grant is recorded as
            user_query = select(UserOrm).where(UserOrm.email == email)
            user_record = await db_session.scalar(user_query)
            if user_record is None:
                raise SystemExit(f"No user with email {email}: they must sign in once first")
            system_user_query = select(UserOrm).where(UserOrm.is_system_user.is_(True))
            system_user_record = await db_session.scalar(system_user_query)
            system_auth_user = AuthUser(
                id=system_user_record.id,
                identity=system_user_record.identity,
                role=RoleType.SYSTEM,
                permissions=frozenset(),
            )

            # Grant the credits, making a reader a creator, as the admin panel does
            credit_ledger_service = CreditLedgerService(db_session=db_session)
            admin_credit_service = AdminCreditService(
                db_session=db_session, credit_ledger_service=credit_ledger_service
            )
            grant_user_credits_input = AdminGrantUserCreditsInput(amount_usd=amount_usd, note=note)
            grant_user_credits_result = await admin_credit_service.grant_user_credits(
                user_record.identity, grant_user_credits_input, system_auth_user
            )
            is_made_creator = grant_user_credits_result.is_made_creator

            # Read the new balance back
            find_credit_balance_result = await credit_ledger_service.find_credit_balance(
                user_record.id
            )
    finally:
        await db_engine.dispose()

    print(f"Granted ${amount_usd} to {email}.")
    print(f"Balance is now ${find_credit_balance_result.credit_balance_usd:.2f}.")
    if is_made_creator:
        print("They're now a creator: they need to sign out and back in to pick up the role.")


def main() -> int:
    """Grants the credits named on the command line and prints the new balance."""
    parsed_arguments = _parse_arguments()
    amount_usd = _parse_amount_usd(parsed_arguments.amount)
    asyncio.run(_grant_credits(parsed_arguments.email, amount_usd, parsed_arguments.note))
    return 0


if __name__ == "__main__":
    sys.exit(main())
