from libs.core.exceptions import UnprocessableException


class BlogPostException(Exception): ...


class BlogPostBodyInvalidException(BlogPostException, UnprocessableException): ...
