from pydantic import BaseModel


class IdentityResponseDto(BaseModel):
    identity: str


class EmptyResponseDto(BaseModel):
    pass
