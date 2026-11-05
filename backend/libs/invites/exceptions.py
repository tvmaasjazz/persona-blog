from libs.core.exceptions import NotFoundException


class InviteException(Exception): ...


class InviteNotFoundException(InviteException, NotFoundException): ...
