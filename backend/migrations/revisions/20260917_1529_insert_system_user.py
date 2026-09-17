from migration_runner import MigrationRunner

revision = "20260917_1529"
down_revision = "20260917_1528"

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    MIGRATION_RUNNER.run_transactional("pb_user/0002_insert_system_user.up.sql")


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional("pb_user/0002_insert_system_user.down.sql")
