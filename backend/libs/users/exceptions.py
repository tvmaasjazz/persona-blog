from libs.core.exceptions import ConflictException, ForbiddenException


class UserException(Exception): ...


class UserInactiveException(UserException, ForbiddenException): ...


class UserEmailTakenException(UserException, ConflictException): ...
