from migration_runner import MigrationRunner

revision = "20260924_2042"
down_revision = "20260924_2041"

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    MIGRATION_RUNNER.run_transactional("pb_llm_call/0002_add_run_and_step_references.up.sql")


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional("pb_llm_call/0002_add_run_and_step_references.down.sql")
