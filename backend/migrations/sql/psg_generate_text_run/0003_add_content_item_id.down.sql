DROP INDEX psg_generate_text_run_content_item_id_idx;

ALTER TABLE psg_generate_text_run
    DROP COLUMN content_item_id;
