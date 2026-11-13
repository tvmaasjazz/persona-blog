from migration_runner import MigrationRunner

revision = "20261103_2241"
down_revision = "20261103_2102"

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    MIGRATION_RUNNER.run_transactional("psg_user/0006_add_credit_balance_usd.up.sql")
    MIGRATION_RUNNER.run_transactional("psg_generate_text_run/0005_add_charge_usd.up.sql")
    MIGRATION_RUNNER.run_transactional("psg_generate_text_step/0002_add_charge_usd.up.sql")
    MIGRATION_RUNNER.run_transactional("psg_credit_ledger/0001_create_psg_credit_ledger.up.sql")


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional("psg_credit_ledger/0001_create_psg_credit_ledger.down.sql")
    MIGRATION_RUNNER.run_transactional("psg_generate_text_step/0002_add_charge_usd.down.sql")
    MIGRATION_RUNNER.run_transactional("psg_generate_text_run/0005_add_charge_usd.down.sql")
    MIGRATION_RUNNER.run_transactional("psg_user/0006_add_credit_balance_usd.down.sql")
