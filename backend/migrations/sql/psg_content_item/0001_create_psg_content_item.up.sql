CREATE TYPE psg_content_type AS ENUM ('BLOG_POST');

CREATE TABLE psg_content_item (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    identity UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    persona_id BIGINT NOT NULL REFERENCES psg_persona (id),
    content_type psg_content_type NOT NULL,
    is_public BOOLEAN NOT NULL DEFAULT false,
    published_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    updated_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    deleted_at TIMESTAMP,
    created_by_id BIGINT NOT NULL REFERENCES psg_user (id),
    updated_by_id BIGINT NOT NULL REFERENCES psg_user (id),
    deleted_by_id BIGINT REFERENCES psg_user (id)
);

CREATE INDEX psg_content_item_created_by_id_created_at_idx
    ON psg_content_item (created_by_id, created_at DESC);

CREATE INDEX psg_content_item_persona_id_created_at_idx
    ON psg_content_item (persona_id, created_at DESC);
