from migration_runner import MigrationRunner

revision = "20261106_1828"
down_revision = "20261105_1605"

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    MIGRATION_RUNNER.run_transactional(
        "psg_content_item_view/0001_create_psg_content_item_view.up.sql"
    )
    MIGRATION_RUNNER.run_transactional(
        "psg_content_item_engagement/0001_create_psg_content_item_engagement.up.sql"
    )
    MIGRATION_RUNNER.run_transactional(
        "psg_content_item_engagement/0002_backfill_psg_content_item_engagement.up.sql"
    )


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional(
        "psg_content_item_engagement/0002_backfill_psg_content_item_engagement.down.sql"
    )
    MIGRATION_RUNNER.run_transactional(
        "psg_content_item_engagement/0001_create_psg_content_item_engagement.down.sql"
    )
    MIGRATION_RUNNER.run_transactional(
        "psg_content_item_view/0001_create_psg_content_item_view.down.sql"
    )
