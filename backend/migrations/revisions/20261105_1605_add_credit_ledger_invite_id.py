from migration_runner import MigrationRunner

revision = "20261105_1605"
down_revision = "20261105_1604"

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    MIGRATION_RUNNER.run_transactional("pb_credit_ledger/0003_add_invite_id.up.sql")


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional("pb_credit_ledger/0003_add_invite_id.down.sql")
