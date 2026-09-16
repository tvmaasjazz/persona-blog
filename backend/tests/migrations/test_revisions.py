import subprocess
import sys
from pathlib import Path

import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory


def test_revision_chain_has_single_head(pytestconfig: pytest.Config) -> None:
    alembic_config = Config(pytestconfig.rootpath / "alembic.ini")
    script_directory = ScriptDirectory.from_config(alembic_config)

    revision_heads = script_directory.get_heads()

    assert len(revision_heads) == 1


def test_every_up_sql_file_has_down_sql_file(pytestconfig: pytest.Config) -> None:
    sql_root_path = pytestconfig.rootpath / "migrations" / "sql"

    up_sql_paths = sorted(sql_root_path.glob("*/*.up.sql"))

    missing_down_sql_paths: list[Path] = []
    for up_sql_path in up_sql_paths:
        down_sql_name = up_sql_path.name.replace(".up.sql", ".down.sql")
        if not up_sql_path.with_name(down_sql_name).exists():
            missing_down_sql_paths.append(up_sql_path)
    assert up_sql_paths != []
    assert missing_down_sql_paths == []


@pytest.mark.migration
@pytest.mark.usefixtures("empty_test_database")
def test_every_revision_downgrades_and_upgrades_again(pytestconfig: pytest.Config) -> None:
    alembic_config = Config(pytestconfig.rootpath / "alembic.ini")
    script_directory = ScriptDirectory.from_config(alembic_config)
    revisions_head_first = list(script_directory.walk_revisions())

    for revision in reversed(revisions_head_first):
        for alembic_arguments in (
            ["upgrade", revision.revision],
            ["downgrade", "-1"],
            ["upgrade", revision.revision],
        ):
            subprocess.run(
                [sys.executable, "-m", "alembic", *alembic_arguments],
                cwd=pytestconfig.rootpath,
                check=True,
            )
