DROP INDEX pb_generate_text_run_persona_id_idx;

ALTER TABLE pb_generate_text_run
    DROP COLUMN persona_id,
    DROP COLUMN tone,
    DROP COLUMN target_audience;

-- persona_id, tone, and target_audience data is lost; persona_info cannot be
-- reconstructed from it.
ALTER TABLE pb_generate_text_run
    ADD COLUMN persona_info TEXT;
