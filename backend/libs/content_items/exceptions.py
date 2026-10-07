from libs.core.exceptions import ConflictException, UnprocessableException


class ContentItemException(Exception): ...


class ContentItemPersonaPrivateException(ContentItemException, UnprocessableException): ...


class ContentItemGenerateTextRunNotCompletedException(ContentItemException, ConflictException): ...


class ContentItemGenerateTextRunPersonaMismatchException(
    ContentItemException, UnprocessableException
): ...


class ContentItemGenerateTextRunAlreadySavedException(ContentItemException, ConflictException): ...
