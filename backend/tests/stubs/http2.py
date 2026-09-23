import httpx2


class Httpx2HandlerStub:
    def __init__(self) -> None:
        self.handle_requests: list[httpx2.Request] = []
        self.handle_responses: list[httpx2.Response] = []
        self.handle_error: Exception | None = None

    def handle(self, http_request: httpx2.Request) -> httpx2.Response:
        self.handle_requests.append(http_request)
        if self.handle_error is not None:
            raise self.handle_error
        return self.handle_responses.pop(0)
