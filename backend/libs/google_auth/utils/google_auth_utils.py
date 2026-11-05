from libs.auth.types import SignInErrorType
from libs.google_auth.constants import SIGN_IN_ERROR_TYPE_BY_EXCEPTION


class GoogleAuthUtils:
    """Static helpers for Google sign-in, such as mapping a failure to the error the frontend
    shows."""

    @staticmethod
    def find_sign_in_error_type(exception: Exception) -> SignInErrorType:
        """Returns the first mapped error type the exception is an instance of; re-raises it
        when none matches."""
        for exception_class, sign_in_error_type in SIGN_IN_ERROR_TYPE_BY_EXCEPTION:
            if isinstance(exception, exception_class):
                return sign_in_error_type
        raise exception

    @staticmethod
    def build_sign_in_error_url(frontend_url: str, sign_in_error_type: SignInErrorType) -> str:
        """Returns the frontend's sign-in page carrying the error code it shows."""
        return f"{frontend_url}/sign-in?error={sign_in_error_type}"
