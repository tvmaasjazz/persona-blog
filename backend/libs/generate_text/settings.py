from pydantic import BaseModel, ConfigDict


class GenerateTextSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    max_rewrite_passes: int = 3
    checkpoint_ttl_minutes: int = 10080
    max_output_format_retries: int = 1
    poll_interval_ms: int = 2000
    lease_seconds: int = 60
    lease_heartbeat_seconds: int = 15
    run_pickup_interval_seconds: int = 30
    max_run_pickups: int = 3
