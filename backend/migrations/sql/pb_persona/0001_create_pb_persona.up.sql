CREATE TABLE pb_persona (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    identity UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    name TEXT NOT NULL,
    bio TEXT NOT NULL,
    avatar_url TEXT,
    background TEXT,
    expertise TEXT,
    writing_style TEXT,
    default_tone TEXT,
    default_target_audience TEXT,
    sample_writing TEXT,
    is_public BOOLEAN NOT NULL DEFAULT false,
    created_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    updated_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    deleted_at TIMESTAMP,
    created_by_id BIGINT NOT NULL REFERENCES pb_user (id),
    updated_by_id BIGINT NOT NULL REFERENCES pb_user (id),
    deleted_by_id BIGINT REFERENCES pb_user (id)
);

CREATE UNIQUE INDEX pb_persona_created_by_id_name_idx
    ON pb_persona (created_by_id, name)
    WHERE deleted_at IS NULL;

CREATE INDEX pb_persona_created_by_id_created_at_idx
    ON pb_persona (created_by_id, created_at DESC);
