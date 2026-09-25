DROP INDEX pb_llm_call_step_id_idx;
DROP INDEX pb_llm_call_run_id_idx;

ALTER TABLE pb_llm_call
    DROP COLUMN step_id,
    DROP COLUMN run_id;
