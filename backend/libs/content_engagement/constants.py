from datetime import UTC, datetime

# The feed score counts publish time from here. The backfill in
# migrations/sql/psg_content_item_engagement/0002_* uses the same moment, so changing
# it means rescoring every row
FEED_SCORE_START_AT = datetime(2026, 1, 1, tzinfo=UTC)
