from migration_runner import MigrationRunner

revision = "20261103_2100"
down_revision = "20261017_0157"

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    MIGRATION_RUNNER.run_transactional("psg_role/0001_create_psg_role.up.sql")
    MIGRATION_RUNNER.run_transactional("psg_permission/0001_create_psg_permission.up.sql")
    MIGRATION_RUNNER.run_transactional("psg_role_permission/0001_create_psg_role_permission.up.sql")
    MIGRATION_RUNNER.run_transactional("psg_user/0003_add_role_id.up.sql")


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional("psg_user/0003_add_role_id.down.sql")
    MIGRATION_RUNNER.run_transactional(
        "psg_role_permission/0001_create_psg_role_permission.down.sql"
    )
    MIGRATION_RUNNER.run_transactional("psg_permission/0001_create_psg_permission.down.sql")
    MIGRATION_RUNNER.run_transactional("psg_role/0001_create_psg_role.down.sql")
