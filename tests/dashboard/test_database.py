import duckdb
import pytest

from dashboard.database import (
    DatabaseUnavailableError,
    get_db_connection,
    is_database_available,
)


def test_is_database_available_non_existent(tmp_path):
    missing_file = tmp_path / "missing.duckdb"
    assert is_database_available(missing_file) is False


def test_is_database_available_existing(tmp_path):
    db_file = tmp_path / "test.duckdb"
    with duckdb.connect(str(db_file)) as con:
        con.execute("CREATE TABLE t (id INT)")
    assert is_database_available(db_file) is True


def test_get_db_connection_missing_raises(tmp_path):
    missing_file = tmp_path / "missing.duckdb"
    with pytest.raises(DatabaseUnavailableError):
        with get_db_connection(missing_file):
            pass


def test_get_db_connection_read_only_prevents_mutation(tmp_path):
    db_file = tmp_path / "test.duckdb"
    with duckdb.connect(str(db_file)) as con:
        con.execute("CREATE TABLE sample (id INT, val VARCHAR)")
        con.execute("INSERT INTO sample VALUES (1, 'demo')")

    with get_db_connection(db_file, read_only=True) as con:
        res = con.execute("SELECT count(*) FROM sample").fetchone()[0]
        assert res == 1
        with pytest.raises(Exception):
            con.execute("INSERT INTO sample VALUES (2, 'mutate')")
