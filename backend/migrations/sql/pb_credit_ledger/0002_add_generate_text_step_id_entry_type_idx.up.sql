CREATE UNIQUE INDEX pb_credit_ledger_generate_text_step_id_entry_type_idx
    ON pb_credit_ledger (generate_text_step_id, entry_type)
    WHERE entry_type IN ('CHARGE', 'REFUND') AND deleted_at IS NULL;
