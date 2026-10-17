ALTER TABLE pb_generate_text_run
    ADD COLUMN lease_owner TEXT,
    ADD COLUMN lease_expires_at TIMESTAMP,
    ADD COLUMN pickup_count INTEGER NOT NULL DEFAULT 0;

CREATE INDEX pb_generate_text_run_lease_expires_at_idx
    ON pb_generate_text_run (lease_expires_at)
    WHERE status IN ('PENDING', 'RUNNING');
