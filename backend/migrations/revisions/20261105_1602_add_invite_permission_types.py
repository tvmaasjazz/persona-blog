from migration_runner import MigrationRunner

revision = "20261105_1602"
down_revision = "20261105_1501"

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    # ADD VALUE commits on its own, since a new value can't be used in the transaction
    # that added it
    MIGRATION_RUNNER.run_non_transactional("psg_permission/0009_add_invite_read_type.up.sql")
    MIGRATION_RUNNER.run_non_transactional("psg_permission/0010_add_invite_write_type.up.sql")


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional("psg_permission/0010_add_invite_write_type.down.sql")
    MIGRATION_RUNNER.run_transactional("psg_permission/0009_add_invite_read_type.down.sql")
