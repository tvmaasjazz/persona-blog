from migration_runner import MigrationRunner

revision = "20261103_2100"
down_revision = "20261017_0157"

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    MIGRATION_RUNNER.run_transactional("pb_role/0001_create_pb_role.up.sql")
    MIGRATION_RUNNER.run_transactional("pb_permission/0001_create_pb_permission.up.sql")
    MIGRATION_RUNNER.run_transactional("pb_role_permission/0001_create_pb_role_permission.up.sql")
    MIGRATION_RUNNER.run_transactional("pb_user/0003_add_role_id.up.sql")


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional("pb_user/0003_add_role_id.down.sql")
    MIGRATION_RUNNER.run_transactional("pb_role_permission/0001_create_pb_role_permission.down.sql")
    MIGRATION_RUNNER.run_transactional("pb_permission/0001_create_pb_permission.down.sql")
    MIGRATION_RUNNER.run_transactional("pb_role/0001_create_pb_role.down.sql")
