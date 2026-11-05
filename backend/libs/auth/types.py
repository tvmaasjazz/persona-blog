from enum import StrEnum


class AuthProviderType(StrEnum):
    GOOGLE = "GOOGLE"


class SignInErrorType(StrEnum):
    ACCOUNT_SUSPENDED = "ACCOUNT_SUSPENDED"
    EMAIL_TAKEN = "EMAIL_TAKEN"
    SIGN_IN_EXPIRED = "SIGN_IN_EXPIRED"
    SIGN_IN_FAILED = "SIGN_IN_FAILED"
