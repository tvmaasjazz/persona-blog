from datetime import UTC, datetime
from unittest.mock import ANY
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from libs.database.orm import PersonaOrm, UserOrm
from tests.factories.personas import insert_persona_row


async def test_create_persona_returns_identity_and_persists_row(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    create_persona_response = await api_client.post(
        "/personas",
        json={
            "name": "Ada the Essayist",
            "bio": "Writes long-form essays on computing history.",
            "avatar_url": "https://example.com/ada.png",
            "background": "Former mathematician.",
            "expertise": "Computing history",
            "writing_style": "Formal",
            "default_tone": "Warm",
            "default_target_audience": "Engineers",
            "sample_writing": "It was a cold morning in London.",
        },
    )

    response_body = create_persona_response.json()
    persona_query = select(PersonaOrm).where(PersonaOrm.identity == response_body["identity"])
    persona_record = await db_session.scalar(persona_query)
    assert create_persona_response.status_code == 201
    assert response_body == {"identity": str(persona_record.identity)}
    assert persona_record.name == "Ada the Essayist"
    assert persona_record.bio == "Writes long-form essays on computing history."
    assert persona_record.avatar_url == "https://example.com/ada.png"
    assert persona_record.background == "Former mathematician."
    assert persona_record.expertise == "Computing history"
    assert persona_record.writing_style == "Formal"
    assert persona_record.default_tone == "Warm"
    assert persona_record.default_target_audience == "Engineers"
    assert persona_record.sample_writing == "It was a cold morning in London."
    assert persona_record.is_public is False
    assert persona_record.created_by_id == signed_in_user.id
    assert persona_record.updated_by_id == signed_in_user.id


async def test_create_persona_optional_fields_omitted_persists_null_fields(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    create_persona_response = await api_client.post(
        "/personas", json={"name": "Ada the Essayist", "bio": "Writes essays."}
    )

    response_body = create_persona_response.json()
    persona_query = select(PersonaOrm).where(PersonaOrm.identity == response_body["identity"])
    persona_record = await db_session.scalar(persona_query)
    assert create_persona_response.status_code == 201
    assert persona_record.avatar_url is None
    assert persona_record.background is None
    assert persona_record.expertise is None
    assert persona_record.writing_style is None
    assert persona_record.default_tone is None
    assert persona_record.default_target_audience is None
    assert persona_record.sample_writing is None
    assert persona_record.is_public is False


async def test_create_persona_is_public_true_persists_is_public(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    create_persona_response = await api_client.post(
        "/personas",
        json={"name": "Ada the Essayist", "bio": "Writes essays.", "is_public": True},
    )

    response_body = create_persona_response.json()
    persona_query = select(PersonaOrm).where(PersonaOrm.identity == response_body["identity"])
    persona_record = await db_session.scalar(persona_query)
    assert create_persona_response.status_code == 201
    assert persona_record.is_public is True


@pytest.mark.usefixtures("signed_in_user")
@pytest.mark.parametrize(
    ("request_body", "expected_error_location"),
    [
        pytest.param({"bio": "Writes essays."}, ["body", "name"], id="missing_name"),
        pytest.param({"name": "Ada the Essayist"}, ["body", "bio"], id="missing_bio"),
    ],
)
async def test_create_persona_invalid_body_returns_422(
    api_client: AsyncClient,
    request_body: dict[str, str],
    expected_error_location: list[str],
) -> None:
    create_persona_response = await api_client.post("/personas", json=request_body)

    response_body = create_persona_response.json()
    assert create_persona_response.status_code == 422
    assert response_body["detail"][0]["loc"] == expected_error_location


@pytest.mark.usefixtures("signed_in_user")
async def test_create_persona_duplicate_name_returns_409(api_client: AsyncClient) -> None:
    await api_client.post("/personas", json={"name": "Ada the Essayist", "bio": "Writes essays."})

    create_persona_response = await api_client.post(
        "/personas", json={"name": "Ada the Essayist", "bio": "Writes more essays."}
    )

    assert create_persona_response.status_code == 409


async def test_create_persona_signed_out_returns_401(api_client: AsyncClient) -> None:
    create_persona_response = await api_client.post(
        "/personas", json={"name": "Ada the Essayist", "bio": "Writes essays."}
    )

    assert create_persona_response.status_code == 401


async def test_find_user_persona_list_returns_only_signed_in_users_live_personas_newest_first(
    api_client: AsyncClient,
    signed_in_user: UserOrm,
    db_session: AsyncSession,
    other_user_client: AsyncClient,
) -> None:
    oldest_persona_record = await insert_persona_row(
        db_session,
        created_by_id=signed_in_user.id,
        name="Oldest Persona",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    newest_persona_record = await insert_persona_row(
        db_session,
        created_by_id=signed_in_user.id,
        name="Newest Persona",
        created_at=datetime(2026, 1, 3, tzinfo=UTC),
    )
    await insert_persona_row(
        db_session,
        created_by_id=signed_in_user.id,
        name="Deleted Persona",
        deleted_at=datetime(2026, 1, 4, tzinfo=UTC),
        deleted_by_id=signed_in_user.id,
    )
    await db_session.commit()
    await other_user_client.post(
        "/personas", json={"name": "Other User Persona", "bio": "Writes essays."}
    )
    await other_user_client.post(
        "/personas",
        json={"name": "Other User Public Persona", "bio": "Writes essays.", "is_public": True},
    )

    find_user_persona_list_response = await api_client.get("/personas")

    assert find_user_persona_list_response.status_code == 200
    assert find_user_persona_list_response.json() == {
        "personas": [
            {
                "identity": str(newest_persona_record.identity),
                "name": "Newest Persona",
                "bio": newest_persona_record.bio,
                "avatar_url": None,
                "background": None,
                "expertise": None,
                "writing_style": None,
                "default_tone": None,
                "default_target_audience": None,
                "sample_writing": None,
                "is_public": False,
                "created_at": ANY,
                "updated_at": ANY,
            },
            {
                "identity": str(oldest_persona_record.identity),
                "name": "Oldest Persona",
                "bio": oldest_persona_record.bio,
                "avatar_url": None,
                "background": None,
                "expertise": None,
                "writing_style": None,
                "default_tone": None,
                "default_target_audience": None,
                "sample_writing": None,
                "is_public": False,
                "created_at": ANY,
                "updated_at": ANY,
            },
        ]
    }


async def test_find_user_persona_list_signed_out_returns_401(api_client: AsyncClient) -> None:
    find_user_persona_list_response = await api_client.get("/personas")

    assert find_user_persona_list_response.status_code == 401


async def test_find_persona_returns_persona_response(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    persona_record = await insert_persona_row(
        db_session,
        created_by_id=signed_in_user.id,
        name="Ada the Essayist",
        bio="Writes essays.",
    )
    await db_session.commit()

    find_persona_response = await api_client.get(f"/personas/{persona_record.identity}")

    assert find_persona_response.status_code == 200
    assert find_persona_response.json() == {
        "identity": str(persona_record.identity),
        "name": "Ada the Essayist",
        "bio": "Writes essays.",
        "avatar_url": None,
        "background": None,
        "expertise": None,
        "writing_style": None,
        "default_tone": None,
        "default_target_audience": None,
        "sample_writing": None,
        "is_public": False,
        "created_at": ANY,
        "updated_at": ANY,
    }


async def test_find_persona_never_inserted_returns_404(
    api_client: AsyncClient, signed_in_user: UserOrm
) -> None:
    find_persona_response = await api_client.get(f"/personas/{uuid4()}")

    assert find_persona_response.status_code == 404


async def test_find_persona_soft_deleted_returns_404(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    persona_record = await insert_persona_row(
        db_session,
        created_by_id=signed_in_user.id,
        deleted_at=datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC),
        deleted_by_id=signed_in_user.id,
    )
    await db_session.commit()

    find_persona_response = await api_client.get(f"/personas/{persona_record.identity}")

    assert find_persona_response.status_code == 404


async def test_find_persona_another_users_private_persona_returns_404(
    api_client: AsyncClient, signed_in_user: UserOrm, other_user_client: AsyncClient
) -> None:
    other_create_response = await other_user_client.post(
        "/personas", json={"name": "Not Yours", "bio": "Writes essays."}
    )
    other_persona_identity = other_create_response.json()["identity"]

    find_persona_response = await api_client.get(f"/personas/{other_persona_identity}")

    assert find_persona_response.status_code == 404


async def test_find_persona_another_users_public_persona_returns_persona_response(
    api_client: AsyncClient, signed_in_user: UserOrm, other_user_client: AsyncClient
) -> None:
    other_create_response = await other_user_client.post(
        "/personas",
        json={"name": "Public Persona", "bio": "Writes public essays.", "is_public": True},
    )
    other_persona_identity = other_create_response.json()["identity"]

    find_persona_response = await api_client.get(f"/personas/{other_persona_identity}")

    assert find_persona_response.status_code == 200
    assert find_persona_response.json() == {
        "identity": other_persona_identity,
        "name": "Public Persona",
        "bio": "Writes public essays.",
        "avatar_url": None,
        "background": None,
        "expertise": None,
        "writing_style": None,
        "default_tone": None,
        "default_target_audience": None,
        "sample_writing": None,
        "is_public": True,
        "created_at": ANY,
        "updated_at": ANY,
    }


@pytest.mark.usefixtures("signed_in_user")
async def test_find_persona_malformed_identity_returns_422(api_client: AsyncClient) -> None:
    find_persona_response = await api_client.get("/personas/not-a-uuid")

    response_body = find_persona_response.json()
    assert find_persona_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["path", "persona_identity"]


async def test_find_persona_signed_out_returns_401(api_client: AsyncClient) -> None:
    find_persona_response = await api_client.get(f"/personas/{uuid4()}")

    assert find_persona_response.status_code == 401


async def test_update_persona_replaces_fields_and_persists(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    persona_record = await insert_persona_row(
        db_session,
        created_by_id=signed_in_user.id,
        name="Old Name",
        bio="Old bio.",
        background="Old background.",
        is_public=True,
    )
    await db_session.commit()

    update_persona_response = await api_client.put(
        f"/personas/{persona_record.identity}",
        json={"name": "New Name", "bio": "New bio."},
    )

    await db_session.refresh(persona_record)
    assert update_persona_response.status_code == 200
    assert update_persona_response.json() == {}
    assert persona_record.name == "New Name"
    assert persona_record.bio == "New bio."
    assert persona_record.background is None
    assert persona_record.is_public is False
    assert persona_record.updated_by_id == signed_in_user.id


async def test_update_persona_without_is_public_resets_is_public_to_false(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    persona_record = await insert_persona_row(
        db_session, created_by_id=signed_in_user.id, is_public=True
    )
    await db_session.commit()

    update_persona_response = await api_client.put(
        f"/personas/{persona_record.identity}",
        json={"name": "New Name", "bio": "New bio."},
    )

    await db_session.refresh(persona_record)
    assert update_persona_response.status_code == 200
    assert persona_record.is_public is False


async def test_update_persona_never_inserted_returns_404(
    api_client: AsyncClient, signed_in_user: UserOrm
) -> None:
    update_persona_response = await api_client.put(
        f"/personas/{uuid4()}", json={"name": "New Name", "bio": "New bio."}
    )

    assert update_persona_response.status_code == 404


async def test_update_persona_another_users_private_persona_returns_404(
    api_client: AsyncClient, signed_in_user: UserOrm, other_user_client: AsyncClient
) -> None:
    other_create_response = await other_user_client.post(
        "/personas", json={"name": "Not Yours", "bio": "Writes essays."}
    )
    other_persona_identity = other_create_response.json()["identity"]

    update_persona_response = await api_client.put(
        f"/personas/{other_persona_identity}", json={"name": "New Name", "bio": "New bio."}
    )

    assert update_persona_response.status_code == 404


async def test_update_persona_another_users_public_persona_returns_403(
    api_client: AsyncClient, signed_in_user: UserOrm, other_user_client: AsyncClient
) -> None:
    other_create_response = await other_user_client.post(
        "/personas", json={"name": "Not Yours", "bio": "Writes essays.", "is_public": True}
    )
    other_persona_identity = other_create_response.json()["identity"]

    update_persona_response = await api_client.put(
        f"/personas/{other_persona_identity}", json={"name": "New Name", "bio": "New bio."}
    )

    assert update_persona_response.status_code == 403


@pytest.mark.usefixtures("signed_in_user")
async def test_update_persona_keeping_its_own_name_returns_200(api_client: AsyncClient) -> None:
    create_response = await api_client.post(
        "/personas", json={"name": "Ada the Essayist", "bio": "Writes essays."}
    )
    persona_identity = create_response.json()["identity"]

    update_persona_response = await api_client.put(
        f"/personas/{persona_identity}",
        json={"name": "Ada the Essayist", "bio": "Writes more essays."},
    )

    assert update_persona_response.status_code == 200
    assert update_persona_response.json() == {}


@pytest.mark.usefixtures("signed_in_user")
async def test_update_persona_duplicate_name_returns_409(api_client: AsyncClient) -> None:
    await api_client.post("/personas", json={"name": "First Persona", "bio": "Bio one."})
    second_create_response = await api_client.post(
        "/personas", json={"name": "Second Persona", "bio": "Bio two."}
    )
    second_persona_identity = second_create_response.json()["identity"]

    update_persona_response = await api_client.put(
        f"/personas/{second_persona_identity}",
        json={"name": "First Persona", "bio": "Bio two."},
    )

    assert update_persona_response.status_code == 409


@pytest.mark.usefixtures("signed_in_user")
@pytest.mark.parametrize(
    ("request_body", "expected_error_location"),
    [
        pytest.param({"bio": "Writes essays."}, ["body", "name"], id="missing_name"),
        pytest.param({"name": "Ada the Essayist"}, ["body", "bio"], id="missing_bio"),
    ],
)
async def test_update_persona_invalid_body_returns_422(
    api_client: AsyncClient,
    request_body: dict[str, str],
    expected_error_location: list[str],
) -> None:
    update_persona_response = await api_client.put(f"/personas/{uuid4()}", json=request_body)

    response_body = update_persona_response.json()
    assert update_persona_response.status_code == 422
    assert response_body["detail"][0]["loc"] == expected_error_location


@pytest.mark.usefixtures("signed_in_user")
async def test_update_persona_malformed_identity_returns_422(api_client: AsyncClient) -> None:
    update_persona_response = await api_client.put(
        "/personas/not-a-uuid", json={"name": "New Name", "bio": "New bio."}
    )

    response_body = update_persona_response.json()
    assert update_persona_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["path", "persona_identity"]


async def test_update_persona_signed_out_returns_401(api_client: AsyncClient) -> None:
    update_persona_response = await api_client.put(
        f"/personas/{uuid4()}", json={"name": "New Name", "bio": "New bio."}
    )

    assert update_persona_response.status_code == 401


async def test_delete_persona_soft_deletes_row_and_becomes_not_found(
    api_client: AsyncClient, signed_in_user: UserOrm, db_session: AsyncSession
) -> None:
    persona_record = await insert_persona_row(db_session, created_by_id=signed_in_user.id)
    await db_session.commit()

    delete_persona_response = await api_client.delete(f"/personas/{persona_record.identity}")

    persona_query = select(PersonaOrm).where(PersonaOrm.identity == persona_record.identity)
    orm_result = await db_session.scalar(persona_query)
    find_persona_response = await api_client.get(f"/personas/{persona_record.identity}")
    assert delete_persona_response.status_code == 200
    assert delete_persona_response.json() == {}
    assert orm_result is None
    assert find_persona_response.status_code == 404


async def test_delete_persona_never_inserted_returns_404(
    api_client: AsyncClient, signed_in_user: UserOrm
) -> None:
    delete_persona_response = await api_client.delete(f"/personas/{uuid4()}")

    assert delete_persona_response.status_code == 404


async def test_delete_persona_another_users_private_persona_returns_404(
    api_client: AsyncClient, signed_in_user: UserOrm, other_user_client: AsyncClient
) -> None:
    other_create_response = await other_user_client.post(
        "/personas", json={"name": "Not Yours", "bio": "Writes essays."}
    )
    other_persona_identity = other_create_response.json()["identity"]

    delete_persona_response = await api_client.delete(f"/personas/{other_persona_identity}")

    assert delete_persona_response.status_code == 404


async def test_delete_persona_another_users_public_persona_returns_403(
    api_client: AsyncClient, signed_in_user: UserOrm, other_user_client: AsyncClient
) -> None:
    other_create_response = await other_user_client.post(
        "/personas", json={"name": "Not Yours", "bio": "Writes essays.", "is_public": True}
    )
    other_persona_identity = other_create_response.json()["identity"]

    delete_persona_response = await api_client.delete(f"/personas/{other_persona_identity}")

    assert delete_persona_response.status_code == 403


@pytest.mark.usefixtures("signed_in_user")
async def test_delete_persona_malformed_identity_returns_422(api_client: AsyncClient) -> None:
    delete_persona_response = await api_client.delete("/personas/not-a-uuid")

    response_body = delete_persona_response.json()
    assert delete_persona_response.status_code == 422
    assert response_body["detail"][0]["loc"] == ["path", "persona_identity"]


async def test_delete_persona_signed_out_returns_401(api_client: AsyncClient) -> None:
    delete_persona_response = await api_client.delete(f"/personas/{uuid4()}")

    assert delete_persona_response.status_code == 401
