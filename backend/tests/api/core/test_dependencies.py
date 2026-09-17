import pytest
from fastapi import FastAPI
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.dependencies import DbSessionDep, DbTransactionDep
from libs.database.orm import UserOrm
from tests.factories.users import insert_user_row


async def test_get_db_session_discards_uncommitted_writes(
    fastapi_app: FastAPI, api_client: AsyncClient, db_session: AsyncSession
) -> None:
    @fastapi_app.post("/insert-user-without-transaction")
    async def insert_user_without_transaction(request_db_session: DbSessionDep) -> None:
        await insert_user_row(request_db_session, email="ada@example.com")

    insert_user_response = await api_client.post("/insert-user-without-transaction")

    user_query = select(UserOrm).where(UserOrm.email == "ada@example.com")
    inserted_user_record = await db_session.scalar(user_query)
    assert insert_user_response.status_code == 200
    assert inserted_user_record is None


async def test_get_db_transaction_commits_writes(
    fastapi_app: FastAPI, api_client: AsyncClient, db_session: AsyncSession
) -> None:
    @fastapi_app.post("/insert-user-in-transaction")
    async def insert_user_in_transaction(request_db_session: DbTransactionDep) -> None:
        await insert_user_row(request_db_session, email="ada@example.com")

    insert_user_response = await api_client.post("/insert-user-in-transaction")

    user_query = select(UserOrm).where(UserOrm.email == "ada@example.com")
    inserted_user_record = await db_session.scalar(user_query)
    assert insert_user_response.status_code == 200
    assert inserted_user_record is not None


async def test_get_db_transaction_rolls_back_on_error(
    fastapi_app: FastAPI, api_client: AsyncClient, db_session: AsyncSession
) -> None:
    @fastapi_app.post("/insert-user-then-fail")
    async def insert_user_then_fail(request_db_session: DbTransactionDep) -> None:
        await insert_user_row(request_db_session, email="ada@example.com")
        raise RuntimeError("fail after insert")

    with pytest.raises(RuntimeError):
        await api_client.post("/insert-user-then-fail")

    user_query = select(UserOrm).where(UserOrm.email == "ada@example.com")
    inserted_user_record = await db_session.scalar(user_query)
    assert inserted_user_record is None
