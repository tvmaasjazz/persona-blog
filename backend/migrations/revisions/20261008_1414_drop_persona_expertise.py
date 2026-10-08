from migration_runner import MigrationRunner

revision = "20261008_1414"
down_revision = "20261007_2208"

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    MIGRATION_RUNNER.run_transactional("pb_persona/0002_drop_expertise.up.sql")


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional("pb_persona/0002_drop_expertise.down.sql")
