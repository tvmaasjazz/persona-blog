from pydantic import BaseModel


class SplitMarkdownPostResult(BaseModel):
    title: str | None
    subtitle: str | None
    body: str
