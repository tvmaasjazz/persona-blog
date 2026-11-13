ALTER TABLE psg_generate_text_run
    DROP COLUMN persona_info;

ALTER TABLE psg_generate_text_run
    ADD COLUMN persona_id BIGINT REFERENCES psg_persona (id),
    ADD COLUMN tone TEXT,
    ADD COLUMN target_audience TEXT;

CREATE INDEX psg_generate_text_run_persona_id_idx
    ON psg_generate_text_run (persona_id);
