from pydantic import BaseModel, ConfigDict


class ContentEngagementSettings(BaseModel):
    model_config = ConfigDict(frozen=True)

    # Engagement points per view, and per whole post read (read percents sum, over 100)
    view_weight: float = 1.0
    read_weight: float = 3.0
    # How much later a post is published before an older one needs ten times its
    # engagement to stay ahead of it in the feed
    feed_score_hours_per_tenfold: float = 24.0
