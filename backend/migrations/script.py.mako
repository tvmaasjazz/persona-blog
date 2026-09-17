from migration_runner import MigrationRunner

revision = "${up_revision}"
down_revision = ${f'"{down_revision}"' if down_revision else None}

MIGRATION_RUNNER = MigrationRunner()


def upgrade() -> None:
    MIGRATION_RUNNER.run_transactional("<table>/<nnnn>_<what_it_does>.up.sql")


def downgrade() -> None:
    MIGRATION_RUNNER.run_transactional("<table>/<nnnn>_<what_it_does>.down.sql")
