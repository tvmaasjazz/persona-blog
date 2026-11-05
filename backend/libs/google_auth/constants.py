from libs.auth.exceptions import AuthSignInStateExpiredException
from libs.auth.types import SignInErrorType
from libs.core.exceptions import (
    ForbiddenException,
    ServiceUnavailableException,
    UnauthorizedException,
)
from libs.users.exceptions import UserEmailTakenException, UserInactiveException

GOOGLE_AUTHORIZATION_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES = ("openid", "email", "profile")
GOOGLE_ISSUERS = ("accounts.google.com", "https://accounts.google.com")

# The sign-in error each failure shows the user, checked in order so a specific exception
# is matched before the standard one it extends
SIGN_IN_ERROR_TYPE_BY_EXCEPTION: tuple[tuple[type[Exception], SignInErrorType], ...] = (
    (UserInactiveException, SignInErrorType.ACCOUNT_SUSPENDED),
    (UserEmailTakenException, SignInErrorType.EMAIL_TAKEN),
    (AuthSignInStateExpiredException, SignInErrorType.SIGN_IN_EXPIRED),
    (UnauthorizedException, SignInErrorType.SIGN_IN_FAILED),
    (ForbiddenException, SignInErrorType.SIGN_IN_FAILED),
    (ServiceUnavailableException, SignInErrorType.SIGN_IN_FAILED),
)

# What a failed sign-in may raise and still redirect, rather than answer 500
SIGN_IN_ERROR_EXCEPTIONS = tuple(
    exception_class for exception_class, _ in SIGN_IN_ERROR_TYPE_BY_EXCEPTION
)
