from migration_runner import MigrationRunner

revision = "20260923_1453"
down_revision = "20260917_1529"

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    MIGRATION_RUNNER.run_transactional("pb_llm_call/0001_create_pb_llm_call.up.sql")


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional("pb_llm_call/0001_create_pb_llm_call.down.sql")
