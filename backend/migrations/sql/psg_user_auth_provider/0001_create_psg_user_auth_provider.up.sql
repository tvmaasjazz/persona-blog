CREATE TYPE psg_auth_provider_type AS ENUM ('GOOGLE');

CREATE TABLE psg_user_auth_provider (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    identity UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    user_id BIGINT NOT NULL REFERENCES psg_user (id) ON DELETE CASCADE,
    provider psg_auth_provider_type NOT NULL,
    provider_subject TEXT NOT NULL,
    email_at_provider CITEXT,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    updated_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    deleted_at TIMESTAMP,
    created_by_id BIGINT NOT NULL REFERENCES psg_user (id),
    updated_by_id BIGINT NOT NULL REFERENCES psg_user (id),
    deleted_by_id BIGINT REFERENCES psg_user (id)
);

CREATE UNIQUE INDEX psg_user_auth_provider_provider_subject_idx
    ON psg_user_auth_provider (provider, provider_subject)
    WHERE deleted_at IS NULL;

CREATE INDEX psg_user_auth_provider_user_id_idx ON psg_user_auth_provider (user_id);
