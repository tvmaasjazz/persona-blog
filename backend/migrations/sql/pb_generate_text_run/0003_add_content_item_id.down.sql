DROP INDEX pb_generate_text_run_content_item_id_idx;

ALTER TABLE pb_generate_text_run
    DROP COLUMN content_item_id;
