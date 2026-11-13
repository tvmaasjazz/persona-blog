CREATE TABLE psg_content_item_engagement (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    identity UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    content_item_id BIGINT NOT NULL UNIQUE REFERENCES psg_content_item (id) ON DELETE CASCADE,
    view_count INT NOT NULL DEFAULT 0,
    read_percent_sum BIGINT NOT NULL DEFAULT 0,
    feed_score DOUBLE PRECISION,
    created_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    updated_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    deleted_at TIMESTAMP,
    created_by_id BIGINT NOT NULL REFERENCES psg_user (id),
    updated_by_id BIGINT NOT NULL REFERENCES psg_user (id),
    deleted_by_id BIGINT REFERENCES psg_user (id)
);

CREATE INDEX psg_content_item_engagement_feed_score_idx
    ON psg_content_item_engagement (feed_score DESC NULLS LAST);
