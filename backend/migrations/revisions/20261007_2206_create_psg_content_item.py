from migration_runner import MigrationRunner

revision = "20261007_2206"
down_revision = "20260930_1920"

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    MIGRATION_RUNNER.run_transactional("psg_content_item/0001_create_psg_content_item.up.sql")


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional("psg_content_item/0001_create_psg_content_item.down.sql")
