from migration_runner import MigrationRunner

revision = "20261017_0157"
down_revision = "20261008_1414"

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    MIGRATION_RUNNER.run_transactional("pb_generate_text_run/0004_add_lease.up.sql")


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional("pb_generate_text_run/0004_add_lease.down.sql")
