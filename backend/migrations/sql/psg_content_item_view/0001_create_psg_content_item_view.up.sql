-- A view is a signed-in user's (created_by_id) or a signed-out visitor's (anonymous_user_key), never both
CREATE TABLE psg_content_item_view (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    identity UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    content_item_id BIGINT NOT NULL REFERENCES psg_content_item (id) ON DELETE CASCADE,
    viewed_on DATE NOT NULL DEFAULT ((now() AT TIME ZONE 'utc')::date),
    read_percent SMALLINT NOT NULL CHECK (read_percent IN (0, 25, 50, 75, 100)),
    anonymous_user_key TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    updated_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    deleted_at TIMESTAMP,
    created_by_id BIGINT REFERENCES psg_user (id),
    updated_by_id BIGINT REFERENCES psg_user (id),
    deleted_by_id BIGINT REFERENCES psg_user (id),
    CONSTRAINT psg_content_item_view_viewer_check
        CHECK ((created_by_id IS NULL) <> (anonymous_user_key IS NULL))
);

-- Named by hand: the generated names would pass 63 characters. Each also covers the
-- content_item_id foreign key.
CREATE UNIQUE INDEX psg_content_item_view_user_viewer_day_idx
    ON psg_content_item_view (content_item_id, created_by_id, viewed_on)
    WHERE created_by_id IS NOT NULL AND deleted_at IS NULL;

CREATE UNIQUE INDEX psg_content_item_view_anonymous_viewer_day_idx
    ON psg_content_item_view (content_item_id, anonymous_user_key, viewed_on)
    WHERE anonymous_user_key IS NOT NULL AND deleted_at IS NULL;
