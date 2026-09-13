from collections.abc import Awaitable, Callable

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from libs.core.exceptions import (
    ConflictException,
    ForbiddenException,
    NotFoundException,
    RateLimitedException,
    ServiceUnavailableException,
    UnauthorizedException,
    UnprocessableException,
)

STATUS_CODE_BY_EXCEPTION: dict[type[Exception], int] = {
    NotFoundException: 404,
    ConflictException: 409,
    UnauthorizedException: 401,
    ForbiddenException: 403,
    UnprocessableException: 422,
    RateLimitedException: 429,
    ServiceUnavailableException: 503,
}


def build_exception_handler(
    status_code: int,
) -> Callable[[Request, Exception], Awaitable[JSONResponse]]:
    async def handle_exception(request: Request, exception: Exception) -> JSONResponse:
        return JSONResponse(status_code=status_code, content={"detail": str(exception)})

    return handle_exception


def register_exception_handlers(fastapi_app: FastAPI) -> None:
    for exception_class, status_code in STATUS_CODE_BY_EXCEPTION.items():
        fastapi_app.add_exception_handler(exception_class, build_exception_handler(status_code))
