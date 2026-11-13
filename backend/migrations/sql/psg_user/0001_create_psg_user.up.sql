CREATE TABLE psg_user (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    identity UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
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
    created_by_id BIGINT REFERENCES psg_user (id),
    updated_by_id BIGINT REFERENCES psg_user (id),
    deleted_by_id BIGINT REFERENCES psg_user (id)
);

CREATE UNIQUE INDEX psg_user_email_idx ON psg_user (email) WHERE deleted_at IS NULL;

CREATE UNIQUE INDEX psg_user_is_system_user_idx ON psg_user (is_system_user) WHERE is_system_user;
