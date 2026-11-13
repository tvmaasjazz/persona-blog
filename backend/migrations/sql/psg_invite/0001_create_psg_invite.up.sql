CREATE TABLE psg_invite (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    identity UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    name TEXT NOT NULL,
    credit_amount_usd NUMERIC(16, 10) NOT NULL CHECK (credit_amount_usd > 0),
    note TEXT,
    code_hash TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMP NOT NULL,
    used_at TIMESTAMP,
    used_by_user_id BIGINT REFERENCES psg_user (id),
    revoked_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    updated_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    deleted_at TIMESTAMP,
    created_by_id BIGINT NOT NULL REFERENCES psg_user (id),
    updated_by_id BIGINT NOT NULL REFERENCES psg_user (id),
    deleted_by_id BIGINT REFERENCES psg_user (id),
    CONSTRAINT psg_invite_used_check CHECK ((used_at IS NULL) = (used_by_user_id IS NULL)),
    CONSTRAINT psg_invite_used_revoked_check CHECK (used_at IS NULL OR revoked_at IS NULL)
);

CREATE INDEX psg_invite_created_at_idx
    ON psg_invite (created_at DESC);
