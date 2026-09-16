from migration_runner import MigrationRunner

revision = "20260916_1934"
down_revision = None

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    MIGRATION_RUNNER.run_transactional("extensions/0001_enable_citext.up.sql")
    MIGRATION_RUNNER.run_transactional("pb_user/0001_create_pb_user.up.sql")
    MIGRATION_RUNNER.run_transactional(
        "pb_user_auth_provider/0001_create_pb_user_auth_provider.up.sql"
    )


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional(
        "pb_user_auth_provider/0001_create_pb_user_auth_provider.down.sql"
    )
    MIGRATION_RUNNER.run_transactional("pb_user/0001_create_pb_user.down.sql")
    MIGRATION_RUNNER.run_transactional("extensions/0001_enable_citext.down.sql")
