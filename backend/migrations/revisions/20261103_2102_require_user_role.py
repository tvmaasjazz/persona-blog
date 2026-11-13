from migration_runner import MigrationRunner

revision = "20261103_2102"
down_revision = "20261103_2101"

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    MIGRATION_RUNNER.run_transactional("psg_user/0005_set_role_id_not_null.up.sql")


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional("psg_user/0005_set_role_id_not_null.down.sql")
