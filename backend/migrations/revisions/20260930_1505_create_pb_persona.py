from migration_runner import MigrationRunner

revision = "20260930_1505"
down_revision = "20260924_2042"

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    MIGRATION_RUNNER.run_transactional("pb_persona/0001_create_pb_persona.up.sql")


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional("pb_persona/0001_create_pb_persona.down.sql")
