from migration_runner import MigrationRunner

revision = "20260930_1920"
down_revision = "20260930_1505"

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    MIGRATION_RUNNER.run_transactional(
        "pb_generate_text_run/0002_replace_persona_info_with_persona.up.sql"
    )


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional(
        "pb_generate_text_run/0002_replace_persona_info_with_persona.down.sql"
    )
