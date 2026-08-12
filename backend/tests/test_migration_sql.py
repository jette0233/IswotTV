from pathlib import Path
import subprocess
import sys


def test_initial_migration_does_not_add_columns_twice():
    backend = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head", "--sql"],
        cwd=backend,
        check=True,
        capture_output=True,
        text=True,
    )
    sql = result.stdout.lower()
    assert "create table courses" in sql
    assert "alter table courses add column address" not in sql
    assert "create table sign_tasks" in sql
