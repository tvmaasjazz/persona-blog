from migration_runner import MigrationRunner

revision = "20260917_1528"
down_revision = "20260917_1527"

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    MIGRATION_RUNNER.run_transactional("psg_user/0001_create_psg_user.up.sql")
    MIGRATION_RUNNER.run_transactional(
        "psg_user_auth_provider/0001_create_psg_user_auth_provider.up.sql"
    )


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional(
        "psg_user_auth_provider/0001_create_psg_user_auth_provider.down.sql"
    )
    MIGRATION_RUNNER.run_transactional("psg_user/0001_create_psg_user.down.sql")
