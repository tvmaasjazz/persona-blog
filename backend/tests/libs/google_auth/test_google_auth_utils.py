import pytest

from libs.auth.exceptions import AuthSignInStateExpiredException
from libs.auth.types import SignInErrorType
from libs.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    ServiceUnavailableException,
    UnauthorizedException,
)
from libs.google_auth.utils import GoogleAuthUtils
from libs.users.exceptions import UserEmailTakenException, UserInactiveException


class ExpiredSignInStateSubclassException(AuthSignInStateExpiredException): ...


@pytest.mark.parametrize(
    ("sign_in_exception", "expected_sign_in_error_type"),
    [
        pytest.param(
            UserInactiveException("inactive"), SignInErrorType.ACCOUNT_SUSPENDED, id="user_inactive"
        ),
        pytest.param(
            UserEmailTakenException("taken"), SignInErrorType.EMAIL_TAKEN, id="user_email_taken"
        ),
        pytest.param(
            AuthSignInStateExpiredException("expired"),
            SignInErrorType.SIGN_IN_EXPIRED,
            id="sign_in_state_expired",
        ),
        pytest.param(
            UnauthorizedException("rejected"), SignInErrorType.SIGN_IN_FAILED, id="unauthorized"
        ),
        pytest.param(
            ForbiddenException("not available"), SignInErrorType.SIGN_IN_FAILED, id="forbidden"
        ),
        pytest.param(
            ServiceUnavailableException("down"),
            SignInErrorType.SIGN_IN_FAILED,
            id="service_unavailable",
        ),
    ],
)
def test_find_sign_in_error_type_mapped_exception_returns_its_error_type(
    sign_in_exception: Exception, expected_sign_in_error_type: SignInErrorType
) -> None:
    sign_in_error_type = GoogleAuthUtils.find_sign_in_error_type(sign_in_exception)

    assert sign_in_error_type == expected_sign_in_error_type


def test_find_sign_in_error_type_subclass_of_specific_entry_returns_specific_error_type() -> None:
    sign_in_exception = ExpiredSignInStateSubclassException("expired")

    sign_in_error_type = GoogleAuthUtils.find_sign_in_error_type(sign_in_exception)

    assert sign_in_error_type == SignInErrorType.SIGN_IN_EXPIRED


@pytest.mark.parametrize(
    "unmapped_exception",
    [
        pytest.param(NotFoundException("missing"), id="not_found"),
        pytest.param(ConflictException("conflict"), id="conflict"),
        pytest.param(ValueError("boom"), id="value_error"),
    ],
)
def test_find_sign_in_error_type_unmapped_exception_is_re_raised(
    unmapped_exception: Exception,
) -> None:
    with pytest.raises(type(unmapped_exception)) as raised_exception_info:
        GoogleAuthUtils.find_sign_in_error_type(unmapped_exception)

    assert raised_exception_info.value is unmapped_exception


def test_build_sign_in_error_url_returns_sign_in_page_with_error_code() -> None:
    sign_in_error_url = GoogleAuthUtils.build_sign_in_error_url(
        "https://app.example.com", SignInErrorType.ACCOUNT_SUSPENDED
    )

    assert sign_in_error_url == "https://app.example.com/sign-in?error=ACCOUNT_SUSPENDED"
