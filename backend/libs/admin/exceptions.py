from libs.core.exceptions import ConflictException


class AdminException(Exception): ...


class AdminCreditGrantSystemUserException(AdminException, ConflictException): ...
