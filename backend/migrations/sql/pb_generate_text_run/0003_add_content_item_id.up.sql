ALTER TABLE pb_generate_text_run
    ADD COLUMN content_item_id BIGINT REFERENCES pb_content_item (id);

CREATE INDEX pb_generate_text_run_content_item_id_idx
    ON pb_generate_text_run (content_item_id);
