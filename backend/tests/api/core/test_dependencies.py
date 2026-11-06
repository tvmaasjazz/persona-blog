from unittest.mock import ANY

import pytest
from fastapi import Depends, FastAPI
from httpx import AsyncClient
from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.requests import Request

from apps.api.core.config import AppSettings
from apps.api.core.dependencies import (
    AnonymousUserKeyDep,
    ClientIpDep,
    DbSessionDep,
    OptionalAuthUserDep,
    get_client_ip,
    require_permissions,
)
from libs.auth.results import AuthUser
from libs.auth.services import AuthSessionService
from libs.database.orm import UserOrm
from libs.permissions.types import PermissionType, RoleType
from libs.users.settings import UserSettings
from tests.factories.auth import build_auth_user
from tests.factories.database import fetch_database_utc_now
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


async def test_get_optional_auth_user_no_cookie_returns_none(
    fastapi_app: FastAPI, api_client: AsyncClient
) -> None:
    @fastapi_app.get("/optional-auth-route")
    async def optional_auth_route(auth_user: OptionalAuthUserDep) -> dict[str, bool]:
        return {"is_signed_in": auth_user is not None}

    optional_auth_response = await api_client.get("/optional-auth-route")

    assert optional_auth_response.status_code == 200
    assert optional_auth_response.json() == {"is_signed_in": False}


async def test_get_optional_auth_user_invalid_session_id_returns_401(
    fastapi_app: FastAPI, api_client: AsyncClient
) -> None:
    @fastapi_app.get("/optional-auth-route")
    async def optional_auth_route(auth_user: OptionalAuthUserDep) -> dict[str, bool]:
        return {"is_signed_in": auth_user is not None}

    api_client.cookies.set("sid", "not-a-real-session-id")

    optional_auth_response = await api_client.get("/optional-auth-route")

    assert optional_auth_response.status_code == 401


async def test_get_optional_auth_user_valid_session_returns_auth_user(
    fastapi_app: FastAPI, api_client: AsyncClient, signed_in_user: UserOrm
) -> None:
    @fastapi_app.get("/optional-auth-route")
    async def optional_auth_route(auth_user: OptionalAuthUserDep) -> AuthUser | None:
        return auth_user

    optional_auth_response = await api_client.get("/optional-auth-route")

    assert optional_auth_response.status_code == 200
    assert optional_auth_response.json() == {
        "id": signed_in_user.id,
        "identity": str(signed_in_user.identity),
        "role": "CREATOR",
        "permissions": ANY,
    }


async def test_get_optional_auth_user_valid_session_records_user_activity(
    fastapi_app: FastAPI,
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    db_session: AsyncSession,
) -> None:
    @fastapi_app.get("/optional-auth-route")
    async def optional_auth_route(auth_user: OptionalAuthUserDep) -> dict[str, bool]:
        return {"is_signed_in": auth_user is not None}

    await api_client.get("/optional-auth-route")

    database_utc_now = await fetch_database_utc_now(db_session)
    last_activity_at_query = select(UserOrm.last_activity_at).where(UserOrm.id == signed_in_user.id)
    persisted_last_activity_at = await db_session.scalar(last_activity_at_query)
    assert persisted_last_activity_at == database_utc_now


async def test_get_client_ip_header_unset_returns_connection_address(
    fastapi_app: FastAPI, api_client: AsyncClient, app_settings: AppSettings
) -> None:
    fastapi_app.state.settings = app_settings.model_copy(update={"users": UserSettings()})

    @fastapi_app.get("/client-ip-route")
    async def client_ip_route(client_ip: ClientIpDep) -> dict[str, str]:
        return {"client_ip": client_ip}

    client_ip_response = await api_client.get(
        "/client-ip-route", headers={"X-Forwarded-For": "1.1.1.1"}
    )

    assert client_ip_response.json() == {"client_ip": "127.0.0.1"}


async def test_get_client_ip_header_set_returns_last_entry(
    fastapi_app: FastAPI, api_client: AsyncClient, app_settings: AppSettings
) -> None:
    fastapi_app.state.settings = app_settings.model_copy(
        update={"users": UserSettings(client_ip_header="X-Forwarded-For")}
    )

    @fastapi_app.get("/client-ip-route")
    async def client_ip_route(client_ip: ClientIpDep) -> dict[str, str]:
        return {"client_ip": client_ip}

    client_ip_response = await api_client.get(
        "/client-ip-route", headers={"X-Forwarded-For": "1.1.1.1, 2.2.2.2"}
    )

    assert client_ip_response.json() == {"client_ip": "2.2.2.2"}


async def test_get_client_ip_header_set_but_missing_returns_connection_address(
    fastapi_app: FastAPI, api_client: AsyncClient, app_settings: AppSettings
) -> None:
    fastapi_app.state.settings = app_settings.model_copy(
        update={"users": UserSettings(client_ip_header="X-Forwarded-For")}
    )

    @fastapi_app.get("/client-ip-route")
    async def client_ip_route(client_ip: ClientIpDep) -> dict[str, str]:
        return {"client_ip": client_ip}

    client_ip_response = await api_client.get("/client-ip-route")

    assert client_ip_response.json() == {"client_ip": "127.0.0.1"}


def test_get_client_ip_no_client_returns_unknown(
    fastapi_app: FastAPI, app_settings: AppSettings
) -> None:
    fastapi_app.state.settings = app_settings.model_copy(update={"users": UserSettings()})
    request = Request({"type": "http", "headers": [], "client": None, "app": fastapi_app})

    client_ip = get_client_ip(request)

    assert client_ip == "unknown"


async def test_get_anonymous_user_key_signed_out_returns_key_string(
    fastapi_app: FastAPI, api_client: AsyncClient
) -> None:
    @fastapi_app.get("/anonymous-user-key-route")
    async def anonymous_user_key_route(anonymous_user_key: AnonymousUserKeyDep) -> dict[str, str]:
        return {"anonymous_user_key": anonymous_user_key or ""}

    anonymous_user_key_response = await api_client.get("/anonymous-user-key-route")

    response_body = anonymous_user_key_response.json()
    assert anonymous_user_key_response.status_code == 200
    assert len(response_body["anonymous_user_key"]) == 64


@pytest.mark.usefixtures("signed_in_user")
async def test_get_anonymous_user_key_signed_in_returns_none(
    fastapi_app: FastAPI, api_client: AsyncClient
) -> None:
    @fastapi_app.get("/anonymous-user-key-route")
    async def anonymous_user_key_route(anonymous_user_key: AnonymousUserKeyDep) -> dict[str, None]:
        return {"anonymous_user_key": anonymous_user_key}

    anonymous_user_key_response = await api_client.get("/anonymous-user-key-route")

    assert anonymous_user_key_response.status_code == 200
    assert anonymous_user_key_response.json() == {"anonymous_user_key": None}
