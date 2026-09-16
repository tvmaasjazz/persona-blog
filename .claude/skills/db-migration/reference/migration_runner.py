import pathlib

import sqlparse
from alembic import op


class MigrationRunner:
    """Executes hand-written SQL files from migrations/sql/ inside Alembic revisions."""

    def __init__(self, migrations_root: str = "sql") -> None:
        self._root_dir = pathlib.Path(__file__).parent / migrations_root

    def run_transactional(self, relative_path: str) -> None:
        """Run every statement in the file inside the migration's transaction."""
        sql_content = self._read_file(relative_path)
        statements = sqlparse.split(sql_content)

        for statement in statements:
            if statement.strip():
                self._execute(statement)

    def run_non_transactional(self, relative_path: str) -> None:
        """Run exactly one statement outside a transaction. Raises on more than one."""
        sql_content = self._read_file(relative_path)
        statements = [statement for statement in sqlparse.split(sql_content) if statement.strip()]

        if len(statements) > 1:
            raise ValueError(
                f"'{relative_path}' contains {len(statements)} statements but is being "
                f"executed non-transactionally. Split it into separate migration files "
                f"to prevent partial schema corruption."
            )

        if not statements:
            return

        with op.get_context().autocommit_block():
            self._execute(statements[0])

    def _execute(self, statement: str) -> None:
        # exec_driver_sql sends the SQL untouched. op.execute() would wrap it in text(),
        # which treats any `:word` in the SQL as a bind parameter.
        op.get_bind().exec_driver_sql(statement)

    def _read_file(self, relative_path: str) -> str:
        file_path = self._root_dir / relative_path
        if not file_path.exists():
            raise FileNotFoundError(f"Migration SQL file not found at: {file_path}")
        return file_path.read_text().strip()
