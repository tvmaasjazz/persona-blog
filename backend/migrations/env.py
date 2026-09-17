import asyncio
import os
from logging.config import fileConfig

from alembic import context
from dotenv import load_dotenv
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

alembic_config = context.config
if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

# Variables already in the environment win over .env, matching AppSettings.
load_dotenv()


def run_migrations(db_connection: Connection) -> None:
    context.configure(connection=db_connection, transaction_per_migration=True)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    db_engine = create_async_engine(os.environ["DATABASE_URL"], poolclass=pool.NullPool)
    async with db_engine.connect() as db_connection:
        await db_connection.run_sync(run_migrations)
    await db_engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("Offline migrations (--sql) are not supported")

asyncio.run(run_migrations_online())
