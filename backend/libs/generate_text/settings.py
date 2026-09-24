from pydantic import BaseModel, ConfigDict


class GenerateTextSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_rewrite_passes: int = 3
    checkpoint_ttl_minutes: int = 10080
