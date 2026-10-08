from libs.core.exceptions import (
    ConflictException,
    ServiceUnavailableException,
    UnprocessableException,
)


class GenerateTextException(Exception): ...


class GenerateTextRunNotPausedException(GenerateTextException, ConflictException): ...


class GenerateTextRunVersionMismatchException(GenerateTextException, ConflictException): ...


class GenerateTextOptionsInvalidException(GenerateTextException, UnprocessableException): ...


class GenerateTextOutputInvalidException(GenerateTextException, ServiceUnavailableException): ...
