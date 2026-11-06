from pydantic import BaseModel


class SplitMarkdownPostResult(BaseModel):
    title: str | None
    subtitle: str | None
    body: str


class PageInfoResult(BaseModel):
    page: int
    page_size: int
    total: int
