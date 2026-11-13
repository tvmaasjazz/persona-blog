from migration_runner import MigrationRunner

revision = "20261105_0326"
down_revision = "20261104_1200"

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    # Each ADD VALUE commits on its own, since a new value can't be used in the
    # transaction that added it
    MIGRATION_RUNNER.run_non_transactional("psg_permission/0003_add_user_read_type.up.sql")
    MIGRATION_RUNNER.run_non_transactional("psg_permission/0004_add_credit_read_type.up.sql")
    MIGRATION_RUNNER.run_non_transactional("psg_permission/0005_add_credit_write_type.up.sql")


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional("psg_permission/0005_add_credit_write_type.down.sql")
    MIGRATION_RUNNER.run_transactional("psg_permission/0004_add_credit_read_type.down.sql")
    MIGRATION_RUNNER.run_transactional("psg_permission/0003_add_user_read_type.down.sql")
