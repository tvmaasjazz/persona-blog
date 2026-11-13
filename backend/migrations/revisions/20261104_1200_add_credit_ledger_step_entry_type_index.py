from migration_runner import MigrationRunner

revision = "20261104_1200"
down_revision = "20261103_2241"

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    MIGRATION_RUNNER.run_transactional(
        "psg_credit_ledger/0002_add_generate_text_step_id_entry_type_idx.up.sql"
    )


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional(
        "psg_credit_ledger/0002_add_generate_text_step_id_entry_type_idx.down.sql"
    )
