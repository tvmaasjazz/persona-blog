from libs.core.exceptions import ConflictException, NotFoundException


class GenerateTextException(Exception): ...


class GenerateTextThreadNotFoundException(GenerateTextException, NotFoundException): ...


class GenerateTextThreadNotPausedException(GenerateTextException, ConflictException): ...
