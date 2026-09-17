import httpx


class HttpHandlerStub:
    def __init__(self) -> None:
        self.handle_requests: list[httpx.Request] = []
        self.handle_responses: list[httpx.Response] = []
        self.handle_error: Exception | None = None

    def handle(self, http_request: httpx.Request) -> httpx.Response:
        self.handle_requests.append(http_request)
        if self.handle_error is not None:
            raise self.handle_error
        return self.handle_responses.pop(0)
