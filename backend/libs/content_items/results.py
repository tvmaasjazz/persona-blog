from uuid import UUID

from pydantic import BaseModel


class CreateContentItemResult(BaseModel):
    id: int
    identity: UUID
