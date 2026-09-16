CREATE TYPE pb_auth_provider_type AS ENUM ('GOOGLE', 'AUTH0');

CREATE TABLE pb_user_auth_provider (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    identity UUID NOT NULL DEFAULT gen_random_uuid(),
    user_id BIGINT NOT NULL,
    provider pb_auth_provider_type NOT NULL,
    provider_subject TEXT NOT NULL,
    email_at_provider CITEXT,
    last_used_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    updated_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    deleted_at TIMESTAMP,
    created_by_id BIGINT NOT NULL,
    updated_by_id BIGINT NOT NULL,
    deleted_by_id BIGINT,
    CONSTRAINT pb_user_auth_provider_pkey PRIMARY KEY (id),
    CONSTRAINT pb_user_auth_provider_identity_key UNIQUE (identity),
    CONSTRAINT pb_user_auth_provider_user_id_fkey
        FOREIGN KEY (user_id) REFERENCES pb_user (id) ON DELETE CASCADE,
    CONSTRAINT pb_user_auth_provider_created_by_id_fkey
        FOREIGN KEY (created_by_id) REFERENCES pb_user (id),
    CONSTRAINT pb_user_auth_provider_updated_by_id_fkey
        FOREIGN KEY (updated_by_id) REFERENCES pb_user (id),
    CONSTRAINT pb_user_auth_provider_deleted_by_id_fkey
        FOREIGN KEY (deleted_by_id) REFERENCES pb_user (id)
);

CREATE UNIQUE INDEX pb_user_auth_provider_provider_subject_idx
    ON pb_user_auth_provider (provider, provider_subject)
    WHERE deleted_at IS NULL;

CREATE INDEX pb_user_auth_provider_user_id_idx ON pb_user_auth_provider (user_id);
