import pytest
from fastapi import Depends, FastAPI
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from apps.api.core.config import AppSettings
from apps.api.core.dependencies import DbSessionDep, require_permissions
from libs.auth.services import AuthSessionService
from libs.database.orm import UserOrm
from libs.permissions.types import PermissionType, RoleType
from tests.factories.auth import build_auth_user
from tests.factories.users import insert_user_row


async def test_get_db_session_commits_writes(
    fastapi_app: FastAPI, api_client: AsyncClient, db_session: AsyncSession
) -> None:
    @fastapi_app.post("/insert-user-in-transaction")
    async def insert_user_in_transaction(request_db_session: DbSessionDep) -> None:
        await insert_user_row(request_db_session, email="ada@example.com")

    insert_user_response = await api_client.post("/insert-user-in-transaction")

    user_query = select(UserOrm).where(UserOrm.email == "ada@example.com")
    inserted_user_record = await db_session.scalar(user_query)
    assert insert_user_response.status_code == 200
    assert inserted_user_record is not None


async def test_get_db_session_rolls_back_on_error(
    fastapi_app: FastAPI, api_client: AsyncClient, db_session: AsyncSession
) -> None:
    @fastapi_app.post("/insert-user-then-fail")
    async def insert_user_then_fail(request_db_session: DbSessionDep) -> None:
        await insert_user_row(request_db_session, email="ada@example.com")
        raise RuntimeError("fail after insert")

    with pytest.raises(RuntimeError):
        await api_client.post("/insert-user-then-fail")

    user_query = select(UserOrm).where(UserOrm.email == "ada@example.com")
    inserted_user_record = await db_session.scalar(user_query)
    assert inserted_user_record is None


@pytest.mark.usefixtures("signed_in_user")
async def test_require_permissions_user_holds_all_returns_200(
    fastapi_app: FastAPI, api_client: AsyncClient
) -> None:
    @fastapi_app.post(
        "/guarded-route",
        dependencies=[
            Depends(
                require_permissions(PermissionType.PERSONA_WRITE, PermissionType.BLOG_POST_WRITE)
            )
        ],
    )
    async def guarded_route() -> None:
        return None

    guarded_route_response = await api_client.post("/guarded-route")

    assert guarded_route_response.status_code == 200


async def test_require_permissions_user_lacks_one_returns_403(
    fastapi_app: FastAPI,
    api_client: AsyncClient,
    db_session: AsyncSession,
    redis_client: Redis,
    app_settings: AppSettings,
) -> None:
    user_record = await insert_user_row(db_session, role=RoleType.CREATOR)
    auth_user = build_auth_user(
        user_id=user_record.id,
        user_identity=user_record.identity,
        permissions=frozenset({PermissionType.PERSONA_WRITE}),
    )
    auth_session_service = AuthSessionService(
        redis_client=redis_client, auth_settings=app_settings.auth
    )
    session_id = await auth_session_service.create_session(auth_user)
    api_client.cookies.set("sid", session_id)

    @fastapi_app.post(
        "/guarded-route",
        dependencies=[
            Depends(
                require_permissions(PermissionType.PERSONA_WRITE, PermissionType.BLOG_POST_WRITE)
            )
        ],
    )
    async def guarded_route() -> None:
        return None

    guarded_route_response = await api_client.post("/guarded-route")

    assert guarded_route_response.status_code == 403


@pytest.mark.usefixtures("signed_in_reader")
async def test_require_permissions_route_body_not_reached_when_forbidden(
    fastapi_app: FastAPI, api_client: AsyncClient
) -> None:
    reached_route_bodies: list[str] = []

    @fastapi_app.post(
        "/guarded-route",
        dependencies=[Depends(require_permissions(PermissionType.PERSONA_WRITE))],
    )
    async def guarded_route() -> None:
        reached_route_bodies.append("guarded-route")

    guarded_route_response = await api_client.post("/guarded-route")

    assert guarded_route_response.status_code == 403
    assert reached_route_bodies == []


async def test_require_permissions_signed_out_returns_401(
    fastapi_app: FastAPI, api_client: AsyncClient
) -> None:
    @fastapi_app.post(
        "/guarded-route",
        dependencies=[Depends(require_permissions(PermissionType.PERSONA_WRITE))],
    )
    async def guarded_route() -> None:
        return None

    guarded_route_response = await api_client.post("/guarded-route")

    assert guarded_route_response.status_code == 401
