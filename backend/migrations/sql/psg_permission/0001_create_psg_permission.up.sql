CREATE TYPE psg_permission_type AS ENUM (
    'PERSONA_READ', 'PERSONA_WRITE', 'BLOG_POST_READ', 'BLOG_POST_WRITE', 'GENERATE_TEXT_RUN_READ', 'GENERATE_TEXT_RUN_WRITE'
);

CREATE TABLE psg_permission (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    identity UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    code psg_permission_type NOT NULL UNIQUE,
    created_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    updated_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    deleted_at TIMESTAMP,
    created_by_id BIGINT NOT NULL REFERENCES psg_user (id),
    updated_by_id BIGINT NOT NULL REFERENCES psg_user (id),
    deleted_by_id BIGINT REFERENCES psg_user (id)
);
