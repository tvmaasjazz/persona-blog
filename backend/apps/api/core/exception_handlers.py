from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from libs.auth.constants import SESSION_COOKIE_NAME
from libs.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    PaymentRequiredException,
    RateLimitedException,
    ServiceUnavailableException,
    UnauthorizedException,
    UnprocessableException,
)

STATUS_CODE_BY_EXCEPTION: dict[type[Exception], int] = {
    NotFoundException: 404,
    ConflictException: 409,
    UnauthorizedException: 401,
    PaymentRequiredException: 402,
    ForbiddenException: 403,
    UnprocessableException: 422,
    RateLimitedException: 429,
    ServiceUnavailableException: 503,
}


def build_exception_handler(
    status_code: int,
) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    """Builds a handler that answers with the status code and the exception message as detail."""

    async def handle_exception(request: Request, exception: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exception)})

    return handle_exception


async def handle_unauthorized_exception(
    request: Request, exception: UnauthorizedException
) -> JSONResponse:
    """Answers 401 and deletes the session cookie, so a stale one stops being sent."""
    json_response = JSONResponse(status_code=401, content={"detail": str(exception)})
    json_response.delete_cookie(SESSION_COOKIE_NAME, path="/")
    return json_response


def register_exception_handlers(fastapi_app: FastAPI) -> None:
    """Registers one handler per standard exception, which its subclasses inherit."""
    for exception_class, status_code in STATUS_CODE_BY_EXCEPTION.items():
        if exception_class is UnauthorizedException:
            continue
        fastapi_app.add_exception_handler(exception_class, build_exception_handler(status_code))
    fastapi_app.add_exception_handler(UnauthorizedException, handle_unauthorized_exception)
