-- With no engagement yet, the score is only its publish time: hours since 2026-01-01
-- over 24, the default score start date and hours-per-tenfold setting.
-- scripts/recompute_feed_scores.py rescores with overridden settings.
INSERT INTO pb_content_item_engagement (
    content_item_id,
    view_count,
    read_percent_sum,
    feed_score,
    created_by_id,
    updated_by_id
)
SELECT
    id,
    0,
    0,
    CASE
        WHEN published_at IS NULL THEN NULL
        ELSE EXTRACT(EPOCH FROM (published_at - TIMESTAMP '2026-01-01 00:00:00')) / 3600.0 / 24.0
    END,
    (SELECT id FROM pb_user WHERE is_system_user),
    (SELECT id FROM pb_user WHERE is_system_user)
FROM pb_content_item;
