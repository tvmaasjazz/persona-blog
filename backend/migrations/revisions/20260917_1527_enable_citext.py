from migration_runner import MigrationRunner

revision = "20260917_1527"
down_revision = None

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    MIGRATION_RUNNER.run_transactional("extensions/0001_enable_citext.up.sql")


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional("extensions/0001_enable_citext.down.sql")
