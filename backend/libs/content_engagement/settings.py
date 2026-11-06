from pydantic import BaseModel, ConfigDict


class ContentEngagementSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    view_weight: float = 1.0
    read_weight: float = 3.0
    feed_score_hours_per_tenfold: float = 24.0
