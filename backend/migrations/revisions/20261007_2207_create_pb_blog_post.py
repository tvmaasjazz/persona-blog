from migration_runner import MigrationRunner

revision = "20261007_2207"
down_revision = "20261007_2206"

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    MIGRATION_RUNNER.run_transactional("pb_blog_post/0001_create_pb_blog_post.up.sql")


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional("pb_blog_post/0001_create_pb_blog_post.down.sql")
