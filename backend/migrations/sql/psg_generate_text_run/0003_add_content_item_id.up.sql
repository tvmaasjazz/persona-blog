ALTER TABLE psg_generate_text_run
    ADD COLUMN content_item_id BIGINT REFERENCES psg_content_item (id);

CREATE INDEX psg_generate_text_run_content_item_id_idx
    ON psg_generate_text_run (content_item_id);
