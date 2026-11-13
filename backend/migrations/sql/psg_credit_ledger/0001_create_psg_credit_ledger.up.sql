CREATE TYPE psg_credit_ledger_entry_type AS ENUM ('GRANT', 'CHARGE', 'REFUND', 'ADJUSTMENT');

CREATE TABLE psg_credit_ledger (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    identity UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    user_id BIGINT NOT NULL REFERENCES psg_user (id),
    amount_usd NUMERIC(16, 10) NOT NULL,
    entry_type psg_credit_ledger_entry_type NOT NULL,
    generate_text_run_id BIGINT REFERENCES psg_generate_text_run (id),
    generate_text_step_id BIGINT REFERENCES psg_generate_text_step (id),
    note TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    updated_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    deleted_at TIMESTAMP,
    created_by_id BIGINT NOT NULL REFERENCES psg_user (id),
    updated_by_id BIGINT NOT NULL REFERENCES psg_user (id),
    deleted_by_id BIGINT REFERENCES psg_user (id)
);

CREATE INDEX psg_credit_ledger_user_id_created_at_idx
    ON psg_credit_ledger (user_id, created_at DESC);

CREATE INDEX psg_credit_ledger_generate_text_run_id_idx
    ON psg_credit_ledger (generate_text_run_id);
