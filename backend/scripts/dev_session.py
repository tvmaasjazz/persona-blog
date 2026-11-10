"""Prints a session id for a seeded user, to sign in as them in a browser or with curl.

Run from backend/ against the database and Redis in .env:

    uv run python -m scripts.dev_session --email dev-creator@example.com

Only the session id goes to stdout; put it in the `sid` cookie.
"""

import argparse
import asyncio
import sys

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine

from apps.api.core.config import AppSettings
from libs.auth.results import AuthUser
from libs.auth.services import AuthSessionService
from libs.database.orm import RoleOrm, UserOrm
from libs.database.session import create_db_session_factory
from libs.permissions.services import PermissionService
from scripts.dev_guard import refuse_outside_local_development


def _parse_arguments() -> argparse.Namespace:
    argument_parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    argument_parser.add_argument("--email", required=True, help="the seeded user's email")
    return argument_parser.parse_args()


async def _mint_session(email: str) -> str:
    app_settings = AppSettings()
    refuse_outside_local_development(app_settings)

    db_engine = create_async_engine(app_settings.database_url)
    db_session_factory = create_db_session_factory(db_engine)
    redis_client = Redis.from_url(app_settings.redis_url)
    try:
        # Find the user and the permissions their role holds
        async with db_session_factory() as db_session:
            user_query = (
                select(UserOrm.id, UserOrm.identity, RoleOrm.code)
                .join(RoleOrm, RoleOrm.id == UserOrm.role_id)
                .where(UserOrm.email == email)
            )
            user_query_result = await db_session.execute(user_query)
            user_row = user_query_result.one_or_none()
            if user_row is None:
                raise SystemExit(
                    f"No user with email {email}: run `uv run python -m scripts.dev_seed` first"
                )
            permission_service = PermissionService(db_session=db_session)
            find_role_permission_list_result = await permission_service.find_role_permission_list(
                user_row.code
            )

        # Store the session in Redis as a sign-in does
        auth_user = AuthUser(
            id=user_row.id,
            identity=user_row.identity,
            role=user_row.code,
            permissions=frozenset(find_role_permission_list_result.permissions),
        )
        auth_session_service = AuthSessionService(
            redis_client=redis_client, auth_settings=app_settings.auth
        )
        return await auth_session_service.create_session(auth_user)
    finally:
        await redis_client.aclose()
        await db_engine.dispose()


def main() -> int:
    """Prints a new session id for the user named on the command line."""
    parsed_arguments = _parse_arguments()
    session_id = asyncio.run(_mint_session(parsed_arguments.email))
    print(session_id)
    return 0


if __name__ == "__main__":
    sys.exit(main())
