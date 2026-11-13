ALTER TABLE psg_credit_ledger ADD COLUMN invite_id BIGINT REFERENCES psg_invite (id);

CREATE UNIQUE INDEX psg_credit_ledger_invite_id_idx
    ON psg_credit_ledger (invite_id)
    WHERE invite_id IS NOT NULL;
