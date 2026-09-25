CREATE TYPE pb_generate_text_step_status_type AS ENUM (
    'RUNNING',
    'SUCCEEDED',
    'FAILED',
    'SKIPPED',
    'AWAITING_REVIEW'
);

CREATE TYPE pb_human_decision_type AS ENUM ('APPROVED', 'REJECTED');

CREATE TABLE pb_generate_text_step (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    identity UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    run_id BIGINT NOT NULL REFERENCES pb_generate_text_run (id) ON DELETE CASCADE,
    seq INTEGER NOT NULL,
    step_name TEXT NOT NULL,
    attempt INTEGER NOT NULL DEFAULT 1,
    status pb_generate_text_step_status_type NOT NULL,
    input JSONB,
    output JSONB,
    llm_call_count INTEGER NOT NULL DEFAULT 0,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd NUMERIC(16, 10) NOT NULL DEFAULT 0,
    duration_ms INTEGER,
    human_decision pb_human_decision_type,
    human_feedback TEXT,
    decided_by_id BIGINT REFERENCES pb_user (id),
    decided_at TIMESTAMP,
    error_code TEXT,
    error_message TEXT,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    updated_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    deleted_at TIMESTAMP,
    created_by_id BIGINT NOT NULL REFERENCES pb_user (id),
    updated_by_id BIGINT NOT NULL REFERENCES pb_user (id),
    deleted_by_id BIGINT REFERENCES pb_user (id),
    CONSTRAINT pb_generate_text_step_run_id_seq_key UNIQUE (run_id, seq)
);

CREATE INDEX pb_generate_text_step_run_id_seq_idx ON pb_generate_text_step (run_id, seq);
