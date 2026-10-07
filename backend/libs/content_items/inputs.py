from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from libs.content_items.types import ContentType


class CreateContentItemInput(BaseModel):
    persona_id: int
    content_type: ContentType
    is_public: bool
    published_at: datetime | None
    generate_text_run_identity: UUID | None


class UpdateContentItemInput(BaseModel):
    is_public: bool
    published_at: datetime | None
