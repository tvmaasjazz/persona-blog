"""Exits non-zero when the migrated database and the Orm metadata disagree."""

import asyncio
import os
import sys
from pprint import pformat

from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from dotenv import load_dotenv
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

import libs.database.orm  # noqa: F401 — registers every Orm class on BaseOrm.metadata
from libs.database.base import BaseOrm

ALEMBIC_VERSION_TABLE_NAME = "alembic_version"


def _include_name(name: str | None, type_: str, parent_names: dict[str, str | None]) -> bool:
    return not (type_ == "table" and name == ALEMBIC_VERSION_TABLE_NAME)


def _compare_schema(db_connection: Connection) -> list[object]:
    migration_context = MigrationContext.configure(
        db_connection, opts={"include_name": _include_name, "compare_type": True}
    )
    return compare_metadata(migration_context, BaseOrm.metadata)


async def _find_schema_differences() -> list[object]:
    db_engine = create_async_engine(os.environ["DATABASE_URL"])
    async with db_engine.connect() as db_connection:
        schema_differences = await db_connection.run_sync(_compare_schema)
    await db_engine.dispose()
    return schema_differences


def main() -> int:
    load_dotenv()
    schema_differences = asyncio.run(_find_schema_differences())
    if schema_differences:
        print("Schema drift between migrations and Orm metadata:", file=sys.stderr)
        print(pformat(schema_differences), file=sys.stderr)
        return 1
    print("No schema drift.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
