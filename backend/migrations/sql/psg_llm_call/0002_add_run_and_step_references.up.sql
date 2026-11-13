ALTER TABLE psg_llm_call
    ADD COLUMN run_id BIGINT REFERENCES psg_generate_text_run (id) ON DELETE SET NULL,
    ADD COLUMN step_id BIGINT REFERENCES psg_generate_text_step (id) ON DELETE SET NULL;

CREATE INDEX psg_llm_call_run_id_idx ON psg_llm_call (run_id);
CREATE INDEX psg_llm_call_step_id_idx ON psg_llm_call (step_id);
