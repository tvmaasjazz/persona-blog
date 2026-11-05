from libs.core.exceptions import UnauthorizedException


class AuthException(Exception): ...


class AuthSignInStateExpiredException(AuthException, UnauthorizedException): ...
