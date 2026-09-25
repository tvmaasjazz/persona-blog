ALTER TABLE pb_llm_call
    ADD COLUMN run_id BIGINT REFERENCES pb_generate_text_run (id) ON DELETE SET NULL,
    ADD COLUMN step_id BIGINT REFERENCES pb_generate_text_step (id) ON DELETE SET NULL;

CREATE INDEX pb_llm_call_run_id_idx ON pb_llm_call (run_id);
CREATE INDEX pb_llm_call_step_id_idx ON pb_llm_call (step_id);
