DROP INDEX psg_llm_call_step_id_idx;
DROP INDEX psg_llm_call_run_id_idx;

ALTER TABLE psg_llm_call
    DROP COLUMN step_id,
    DROP COLUMN run_id;
