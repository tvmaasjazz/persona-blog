from migration_runner import MigrationRunner

revision = "20260924_2041"
down_revision = "20260923_1453"

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    MIGRATION_RUNNER.run_transactional(
        "pb_generate_text_run/0001_create_pb_generate_text_run.up.sql"
    )
    MIGRATION_RUNNER.run_transactional(
        "pb_generate_text_step/0001_create_pb_generate_text_step.up.sql"
    )


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional(
        "pb_generate_text_step/0001_create_pb_generate_text_step.down.sql"
    )
    MIGRATION_RUNNER.run_transactional(
        "pb_generate_text_run/0001_create_pb_generate_text_run.down.sql"
    )
