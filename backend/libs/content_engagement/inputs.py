from pydantic import BaseModel


class RecordContentViewInput(BaseModel):
    content_item_id: int
    read_percent: int
    anonymous_user_key: str | None
