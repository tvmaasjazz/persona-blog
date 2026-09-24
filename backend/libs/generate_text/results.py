from uuid import UUID

from pydantic import BaseModel

from libs.generate_text.types import GenerateTextStatusType


class GenerateTextResult(BaseModel):
    thread_identity: UUID
    status: GenerateTextStatusType
    content: str
    character_count: int
