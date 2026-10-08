from libs.core.exceptions import ConflictException, UnprocessableException


class ContentItemPersonaPrivateException(UnprocessableException): ...


class ContentItemGenerateTextRunNotCompletedException(ConflictException): ...


class ContentItemGenerateTextRunAlreadySavedException(ConflictException): ...
