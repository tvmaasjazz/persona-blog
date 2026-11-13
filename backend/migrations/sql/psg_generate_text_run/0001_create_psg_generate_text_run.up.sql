CREATE TYPE psg_text_type AS ENUM ('BLOG_POST');

CREATE TYPE psg_generate_text_run_status_type AS ENUM (
    'PENDING',
    'RUNNING',
    'AWAITING_REVIEW',
    'COMPLETED',
    'FAILED',
    'CANCELLED'
);

CREATE TABLE psg_generate_text_run (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    identity UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    text_type psg_text_type NOT NULL,
    graph_name TEXT NOT NULL,
    graph_version TEXT NOT NULL,
    status psg_generate_text_run_status_type NOT NULL DEFAULT 'PENDING',
    prompt_text TEXT NOT NULL,
    persona_info TEXT,
    additional_context TEXT,
    options JSONB NOT NULL,
    error_code TEXT,
    error_message TEXT,
    llm_call_count INTEGER NOT NULL DEFAULT 0,
    input_tokens INTEGER NOT NULL DEFAULT 0,
    output_tokens INTEGER NOT NULL DEFAULT 0,
    cost_usd NUMERIC(16, 10) NOT NULL DEFAULT 0,
    started_at TIMESTAMP,
    finished_at TIMESTAMP,
    created_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    updated_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    deleted_at TIMESTAMP,
    created_by_id BIGINT NOT NULL REFERENCES psg_user (id),
    updated_by_id BIGINT NOT NULL REFERENCES psg_user (id),
    deleted_by_id BIGINT REFERENCES psg_user (id)
);

CREATE INDEX psg_generate_text_run_created_by_id_created_at_idx
    ON psg_generate_text_run (created_by_id, created_at DESC);

CREATE INDEX psg_generate_text_run_status_idx
    ON psg_generate_text_run (status)
    WHERE status IN ('PENDING', 'RUNNING', 'AWAITING_REVIEW');
