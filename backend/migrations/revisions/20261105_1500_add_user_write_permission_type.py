from migration_runner import MigrationRunner

revision = "20261105_1500"
down_revision = "20261105_0327"

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    # ADD VALUE commits on its own, since a new value can't be used in the transaction
    # that added it
    MIGRATION_RUNNER.run_non_transactional("psg_permission/0007_add_user_write_type.up.sql")


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional("psg_permission/0007_add_user_write_type.down.sql")
