ALTER TABLE pb_generate_text_run
    DROP COLUMN persona_info;

ALTER TABLE pb_generate_text_run
    ADD COLUMN persona_id BIGINT REFERENCES pb_persona (id),
    ADD COLUMN tone TEXT,
    ADD COLUMN target_audience TEXT;

CREATE INDEX pb_generate_text_run_persona_id_idx
    ON pb_generate_text_run (persona_id);
