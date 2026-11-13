CREATE TYPE psg_llm_type AS ENUM ('FAST', 'STRONG', 'THINKING');
CREATE TYPE psg_llm_provider_type AS ENUM ('OPENAI', 'ANTHROPIC');
CREATE TYPE psg_llm_call_status_type AS ENUM ('PENDING', 'SUCCEEDED', 'INCOMPLETE', 'FAILED');
CREATE TYPE psg_llm_call_reason_type AS ENUM (
    'MAX_TOKENS',
    'CONTENT_FILTER',
    'REFUSAL',
    'PROVIDER_ERROR',
    'PROVIDER_UNAVAILABLE',
    'RATE_LIMITED',
    'CANCELLED',
    'NOT_FINISHED'
);

CREATE TABLE psg_llm_call (
    id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    identity UUID NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    llm_type psg_llm_type NOT NULL,
    provider psg_llm_provider_type NOT NULL,
    model_name TEXT NOT NULL,
    purpose TEXT NOT NULL,
    system_prompt TEXT,
    user_prompt TEXT NOT NULL,
    response_text TEXT,
    response_json JSONB,
    reason psg_llm_call_reason_type,
    status psg_llm_call_status_type NOT NULL DEFAULT 'PENDING',
    input_tokens INTEGER,
    output_tokens INTEGER,
    cached_input_tokens INTEGER,
    reasoning_tokens INTEGER,
    cost_usd NUMERIC(16, 10),
    duration_ms INTEGER,
    error_code TEXT,
    error_message TEXT,
    provider_error_message TEXT,
    provider_request_reference TEXT,
    created_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    updated_at TIMESTAMP NOT NULL DEFAULT (now() AT TIME ZONE 'utc'),
    deleted_at TIMESTAMP,
    created_by_id BIGINT NOT NULL REFERENCES psg_user (id),
    updated_by_id BIGINT NOT NULL REFERENCES psg_user (id),
    deleted_by_id BIGINT REFERENCES psg_user (id)
);

CREATE INDEX psg_llm_call_created_by_id_idx ON psg_llm_call (created_by_id);
