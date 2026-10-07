from migration_runner import MigrationRunner

revision = "20261007_2208"
down_revision = "20261007_2207"

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    MIGRATION_RUNNER.run_transactional("pb_generate_text_run/0003_add_content_item_id.up.sql")


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional("pb_generate_text_run/0003_add_content_item_id.down.sql")
