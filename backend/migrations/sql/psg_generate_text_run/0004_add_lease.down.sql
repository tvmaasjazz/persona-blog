DROP INDEX psg_generate_text_run_lease_expires_at_idx;

ALTER TABLE psg_generate_text_run
    DROP COLUMN pickup_count,
    DROP COLUMN lease_expires_at,
    DROP COLUMN lease_owner;
