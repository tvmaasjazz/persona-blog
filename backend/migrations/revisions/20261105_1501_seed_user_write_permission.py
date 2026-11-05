from migration_runner import MigrationRunner

revision = "20261105_1501"
down_revision = "20261105_1500"

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    MIGRATION_RUNNER.run_transactional("pb_permission/0008_insert_user_write_permission.up.sql")
    MIGRATION_RUNNER.run_transactional("pb_role_permission/0004_grant_user_write_permission.up.sql")


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional(
        "pb_role_permission/0004_grant_user_write_permission.down.sql"
    )
    MIGRATION_RUNNER.run_transactional("pb_permission/0008_insert_user_write_permission.down.sql")
