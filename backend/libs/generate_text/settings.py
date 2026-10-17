from pydantic import BaseModel, ConfigDict


class GenerateTextSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_rewrite_passes: int = 3
    checkpoint_ttl_minutes: int = 10080
    max_output_format_retries: int = 1
    poll_interval_ms: int = 2000
