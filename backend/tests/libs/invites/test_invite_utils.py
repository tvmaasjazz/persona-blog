import re
from datetime import UTC, datetime

import pytest

from libs.invites.types import InviteSignInResultType, InviteStatusType
from libs.invites.utils import InviteUtils

PAST = datetime(2026, 1, 2, tzinfo=UTC)
URL_SAFE_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


def test_hash_code_returns_sha256_hex_digest() -> None:
    code_hash = InviteUtils.hash_code("abc")

    assert code_hash == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"


def test_build_code_returns_url_safe_code_of_expected_length() -> None:
    code = InviteUtils.build_code()

    assert len(code) == 22
    assert URL_SAFE_PATTERN.match(code) is not None


def test_build_code_two_calls_produce_different_codes() -> None:
    first_code = InviteUtils.build_code()
    second_code = InviteUtils.build_code()

    assert first_code != second_code


def test_build_invite_url_joins_frontend_url_and_code() -> None:
    invite_url = InviteUtils.build_invite_url("https://app.example.com", "abc-123")

    assert invite_url == "https://app.example.com/invite/abc-123"


@pytest.mark.parametrize(
    ("revoked_at", "used_at", "is_expired", "expected_status_type"),
    [
        pytest.param(None, None, False, InviteStatusType.UNUSED, id="unused"),
        pytest.param(None, None, True, InviteStatusType.EXPIRED, id="expired"),
        pytest.param(None, PAST, False, InviteStatusType.USED, id="used"),
        pytest.param(PAST, None, False, InviteStatusType.REVOKED, id="revoked"),
        pytest.param(None, PAST, True, InviteStatusType.USED, id="used_wins_over_expired"),
        pytest.param(PAST, PAST, False, InviteStatusType.REVOKED, id="revoked_wins_over_used"),
        pytest.param(PAST, None, True, InviteStatusType.REVOKED, id="revoked_wins_over_expired"),
    ],
)
def test_build_status_type_returns_status_by_precedence(
    revoked_at: datetime | None,
    used_at: datetime | None,
    is_expired: bool,
    expected_status_type: InviteStatusType,
) -> None:
    status_type = InviteUtils.build_status_type(revoked_at, used_at, is_expired)

    assert status_type == expected_status_type


@pytest.mark.parametrize(
    ("status_type", "expected_sign_in_result_type"),
    [
        pytest.param(InviteStatusType.USED, InviteSignInResultType.INVITE_USED, id="used"),
        pytest.param(InviteStatusType.EXPIRED, InviteSignInResultType.INVITE_EXPIRED, id="expired"),
        pytest.param(InviteStatusType.REVOKED, InviteSignInResultType.INVITE_REVOKED, id="revoked"),
    ],
)
def test_build_sign_in_result_type_returns_result_for_each_stopping_status(
    status_type: InviteStatusType, expected_sign_in_result_type: InviteSignInResultType
) -> None:
    sign_in_result_type = InviteUtils.build_sign_in_result_type(status_type)

    assert sign_in_result_type == expected_sign_in_result_type


def test_build_sign_in_result_type_unused_raises_not_implemented_error() -> None:
    with pytest.raises(NotImplementedError):
        InviteUtils.build_sign_in_result_type(InviteStatusType.UNUSED)


def test_build_sign_in_redirect_url_without_invite_returns_frontend_url() -> None:
    redirect_url = InviteUtils.build_sign_in_redirect_url("https://app.example.com", None)

    assert redirect_url == "https://app.example.com"


def test_build_sign_in_redirect_url_accepted_returns_sign_in_page_with_invite() -> None:
    redirect_url = InviteUtils.build_sign_in_redirect_url(
        "https://app.example.com", InviteSignInResultType.ACCEPTED
    )

    assert redirect_url == "https://app.example.com/sign-in?invite=ACCEPTED"


@pytest.mark.parametrize(
    ("invite_sign_in_result_type", "expected_redirect_url"),
    [
        pytest.param(
            InviteSignInResultType.INVITE_NOT_FOUND,
            "https://app.example.com/sign-in?invite_error=INVITE_NOT_FOUND",
            id="not_found",
        ),
        pytest.param(
            InviteSignInResultType.INVITE_USED,
            "https://app.example.com/sign-in?invite_error=INVITE_USED",
            id="used",
        ),
        pytest.param(
            InviteSignInResultType.INVITE_EXPIRED,
            "https://app.example.com/sign-in?invite_error=INVITE_EXPIRED",
            id="expired",
        ),
        pytest.param(
            InviteSignInResultType.INVITE_REVOKED,
            "https://app.example.com/sign-in?invite_error=INVITE_REVOKED",
            id="revoked",
        ),
    ],
)
def test_build_sign_in_redirect_url_error_returns_sign_in_page_with_invite_error(
    invite_sign_in_result_type: InviteSignInResultType, expected_redirect_url: str
) -> None:
    redirect_url = InviteUtils.build_sign_in_redirect_url(
        "https://app.example.com", invite_sign_in_result_type
    )

    assert redirect_url == expected_redirect_url
