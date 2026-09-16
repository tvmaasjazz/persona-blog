CREATE TABLE pb_user (
    id BIGINT GENERATED ALWAYS AS IDENTITY,
    identity UUID NOT NULL DEFAULT gen_random_uuid(),
    email CITEXT NOT NULL,
    is_email_verified BOOLEAN NOT NULL DEFAULT false,
    display_name TEXT,
    avatar_url TEXT,
    is_active BOOLEAN NOT NULL DEFAULT true,
    is_system_user BOOLEAN NOT NULL DEFAULT false,
    last_login_at TIMESTAMP,
    last_activity_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    updated_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    deleted_at TIMESTAMP,
    created_by_id BIGINT,
    updated_by_id BIGINT,
    deleted_by_id BIGINT,
    CONSTRAINT pb_user_pkey PRIMARY KEY (id),
    CONSTRAINT pb_user_identity_key UNIQUE (identity),
    CONSTRAINT pb_user_created_by_id_fkey FOREIGN KEY (created_by_id) REFERENCES pb_user (id),
    CONSTRAINT pb_user_updated_by_id_fkey FOREIGN KEY (updated_by_id) REFERENCES pb_user (id),
    CONSTRAINT pb_user_deleted_by_id_fkey FOREIGN KEY (deleted_by_id) REFERENCES pb_user (id)
);

CREATE UNIQUE INDEX pb_user_email_idx ON pb_user (email) WHERE deleted_at IS NULL;

CREATE UNIQUE INDEX pb_user_is_system_user_idx ON pb_user (is_system_user) WHERE is_system_user;
