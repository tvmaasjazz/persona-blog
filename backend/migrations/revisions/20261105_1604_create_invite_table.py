from migration_runner import MigrationRunner

revision = "20261105_1604"
down_revision = "20261105_1603"

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    MIGRATION_RUNNER.run_transactional("pb_invite/0001_create_pb_invite.up.sql")


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional("pb_invite/0001_create_pb_invite.down.sql")
