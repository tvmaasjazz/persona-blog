CREATE TABLE psg_role_permission (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    identity UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    role_id BIGINT NOT NULL REFERENCES psg_role (id),
    permission_id BIGINT NOT NULL REFERENCES psg_permission (id),
    created_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    updated_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    deleted_at TIMESTAMP,
    created_by_id BIGINT NOT NULL REFERENCES psg_user (id),
    updated_by_id BIGINT NOT NULL REFERENCES psg_user (id),
    deleted_by_id BIGINT REFERENCES psg_user (id),
    CONSTRAINT psg_role_permission_role_id_permission_id_key UNIQUE (role_id, permission_id)
);
