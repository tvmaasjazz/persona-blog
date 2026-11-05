from migration_runner import MigrationRunner

revision = "20261105_1603"
down_revision = "20261105_1602"

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    MIGRATION_RUNNER.run_transactional("pb_permission/0011_insert_invite_permissions.up.sql")
    MIGRATION_RUNNER.run_transactional("pb_role_permission/0005_grant_invite_permissions.up.sql")


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional("pb_role_permission/0005_grant_invite_permissions.down.sql")
    MIGRATION_RUNNER.run_transactional("pb_permission/0011_insert_invite_permissions.down.sql")
