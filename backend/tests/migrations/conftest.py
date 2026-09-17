import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


@pytest.fixture
async def empty_test_database(db_engine: AsyncEngine) -> None:
    async with db_engine.begin() as db_connection:
        await db_connection.execute(text("DROP SCHEMA public CASCADE"))
        await db_connection.execute(text("CREATE SCHEMA public"))
