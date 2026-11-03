from migration_runner import MigrationRunner

revision = "20261103_2101"
down_revision = "20261103_2100"

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    MIGRATION_RUNNER.run_transactional("pb_role/0002_insert_roles.up.sql")
    MIGRATION_RUNNER.run_transactional("pb_permission/0002_insert_permissions.up.sql")
    MIGRATION_RUNNER.run_transactional(
        "pb_role_permission/0002_insert_admin_and_creator_permissions.up.sql"
    )
    MIGRATION_RUNNER.run_transactional("pb_user/0004_backfill_role_id.up.sql")


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional("pb_user/0004_backfill_role_id.down.sql")
    MIGRATION_RUNNER.run_transactional(
        "pb_role_permission/0002_insert_admin_and_creator_permissions.down.sql"
    )
    MIGRATION_RUNNER.run_transactional("pb_permission/0002_insert_permissions.down.sql")
    MIGRATION_RUNNER.run_transactional("pb_role/0002_insert_roles.down.sql")
