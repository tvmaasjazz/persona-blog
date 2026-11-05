ALTER TABLE pb_credit_ledger ADD COLUMN invite_id BIGINT REFERENCES pb_invite (id);

CREATE UNIQUE INDEX pb_credit_ledger_invite_id_idx
    ON pb_credit_ledger (invite_id)
    WHERE invite_id IS NOT NULL;
