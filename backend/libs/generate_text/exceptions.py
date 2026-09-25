from libs.core.exceptions import ConflictException


class GenerateTextException(Exception): ...


class GenerateTextRunNotPausedException(GenerateTextException, ConflictException): ...


class GenerateTextRunVersionMismatchException(GenerateTextException, ConflictException): ...
