from migration_runner import MigrationRunner

revision = "20261105_0327"
down_revision = "20261105_0326"

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    MIGRATION_RUNNER.run_transactional("psg_permission/0006_insert_admin_permissions.up.sql")
    MIGRATION_RUNNER.run_transactional("psg_role_permission/0003_grant_admin_permissions.up.sql")


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional("psg_role_permission/0003_grant_admin_permissions.down.sql")
    MIGRATION_RUNNER.run_transactional("psg_permission/0006_insert_admin_permissions.down.sql")
