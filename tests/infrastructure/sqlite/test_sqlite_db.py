"""Tests for SqliteDatabase setup and connection management."""

import re
import sqlite3
from pathlib import Path

import pytest

from niveshpy.exceptions import DatabaseError, IntegrityError
from niveshpy.infrastructure.sqlite.sqlite_db import SqliteDatabase, _iregexp

# ---------------------------------------------------------------------------
# _iregexp function
# ---------------------------------------------------------------------------


class TestIregexpFunction:
    """Test _iregexp custom SQLite function."""

    @pytest.mark.parametrize(
        "pattern,value,expected",
        [
            ("test", "test", True),
            ("test", "TEST", True),
            ("TEST", "test", True),
            ("TeSt", "tEsT", True),
            ("hello", "world", False),
            ("^test$", "test", True),
            ("^test$", "testing", False),
            ("test.*", "test123", True),
            ("fo+", "foobar", True),
            ("[0-9]+", "abc123def", True),
            ("[0-9]+", "abcdef", False),
            ("test|hello", "hello world", True),
            ("test|hello", "goodbye", False),
        ],
        ids=[
            "exact_match",
            "case_insensitive_upper",
            "case_insensitive_lower",
            "case_insensitive_mixed",
            "no_match",
            "anchor_match",
            "anchor_no_match",
            "wildcard_match",
            "quantifier_match",
            "character_class_match",
            "character_class_no_match",
            "alternation_match",
            "alternation_no_match",
        ],
    )
    def test_basic_regex_patterns(self, pattern, value, expected):
        """Test _iregexp with various regex patterns."""
        assert _iregexp(pattern, value) == expected

    def test_none_value_returns_false(self):
        """Test that None value returns False."""
        assert _iregexp("test", None) is False

    @pytest.mark.parametrize(
        "pattern,value,expected",
        [
            ("", "test", True),
            ("", "", True),
            ("test", "", False),
            (".*", "", True),
        ],
        ids=["empty_pattern", "both_empty", "empty_value", "wildcard_empty_value"],
    )
    def test_empty_strings(self, pattern, value, expected):
        """Test _iregexp with empty strings."""
        assert _iregexp(pattern, value) == expected

    def test_unicode_characters(self):
        """Test _iregexp with unicode characters."""
        assert _iregexp("café", "CAFÉ") is True
        assert _iregexp("naïve", "NAÏVE") is True
        assert _iregexp("₹", "₹1000") is True
        assert _iregexp("😀", "hello 😀") is True

    def test_multiline_strings(self):
        """Test _iregexp with multiline strings."""
        value = "line1\nline2\nline3"
        assert _iregexp("line2", value) is True
        assert _iregexp("^line2", value) is False
        assert _iregexp("line2", value) is True

    def test_special_regex_characters(self):
        """Test _iregexp with special regex characters."""
        assert _iregexp(r"\d+", "test123") is True
        assert _iregexp(r"\w+", "test_var") is True
        assert _iregexp(r"\s+", "hello world") is True
        assert _iregexp(r"test\.com", "test.com") is True

    def test_invalid_regex_raises_error(self):
        """Test that invalid regex pattern raises error."""
        with pytest.raises(re.error):
            _iregexp("[invalid", "test")

    def test_very_long_strings(self):
        """Test _iregexp with very long strings."""
        long_value = "a" * 10000 + "test" + "b" * 10000
        assert _iregexp("test", long_value) is True


# ---------------------------------------------------------------------------
# _iregexp in SQL
# ---------------------------------------------------------------------------


class TestIregexpInSQL:
    """Test _iregexp function integration with SQLite."""

    @pytest.fixture
    def sql_db(self):
        """Create an in-memory SqliteDatabase with iregexp registered."""
        db = SqliteDatabase(db_path=Path(":memory:"))
        db.initialize()
        return db

    def test_iregexp_function_callable(self, sql_db):
        """Test that iregexp function is directly callable in SQL."""
        result = sql_db.connection.execute(
            "SELECT iregexp(?, ?)", ("test", "TEST")
        ).fetchone()
        assert result[0] == 1

    def test_iregexp_in_where_clause(self, sql_db):
        """Test that iregexp works in SQL WHERE clause."""
        conn = sql_db.connection
        conn.execute(
            "INSERT INTO security (key, name, type, category, properties) VALUES (?, ?, ?, ?, ?)",
            ("TEST1", "Test Security One", "stock", "equity", "{}"),
        )
        conn.execute(
            "INSERT INTO security (key, name, type, category, properties) VALUES (?, ?, ?, ?, ?)",
            ("TEST2", "Another Security", "stock", "equity", "{}"),
        )
        conn.commit()

        results = conn.execute(
            "SELECT key FROM security WHERE iregexp(?, name)", ("test",)
        ).fetchall()

        assert len(results) == 1
        assert results[0][0] == "TEST1"

    def test_iregexp_case_insensitive_in_sql(self, sql_db):
        """Test case-insensitive matching in SQL queries."""
        conn = sql_db.connection
        conn.execute(
            "INSERT INTO account (name, institution, properties) VALUES (?, ?, ?)",
            ("Savings Account", "Bank A", "{}"),
        )
        conn.execute(
            "INSERT INTO account (name, institution, properties) VALUES (?, ?, ?)",
            ("checking account", "Bank B", "{}"),
        )
        conn.execute(
            "INSERT INTO account (name, institution, properties) VALUES (?, ?, ?)",
            ("INVESTMENT ACCOUNT", "Bank C", "{}"),
        )
        conn.commit()

        results = conn.execute(
            "SELECT name FROM account WHERE iregexp(?, name)", ("savings",)
        ).fetchall()

        assert len(results) == 1
        assert results[0][0] == "Savings Account"


# ---------------------------------------------------------------------------
# SqliteDatabase
# ---------------------------------------------------------------------------


@pytest.fixture
def memory_db():
    """Create an in-memory SqliteDatabase."""
    db = SqliteDatabase(db_path=Path(":memory:"))
    db.initialize()
    return db


def _get_table_names(db: SqliteDatabase) -> set[str]:
    """Get table names from the database using sqlite3 introspection."""
    rows = db.connection.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
    ).fetchall()
    return {row[0] for row in rows}


def _get_column_names(db: SqliteDatabase, table: str) -> set[str]:
    """Get column names for a table using PRAGMA."""
    rows = db.connection.execute(f"PRAGMA table_info({table})").fetchall()  # noqa: S608
    return {row[1] for row in rows}


class TestSqliteDatabase:
    """Tests for SqliteDatabase initialization and setup."""

    def test_creates_db_directory(self, tmp_path):
        """Test that SqliteDatabase creates the parent directory on initialize."""
        db_path = tmp_path / "subdir" / "niveshpy.db"
        db = SqliteDatabase(db_path=db_path)
        db.initialize()
        assert db_path.parent.exists()

    def test_creates_connection(self):
        """Test that SqliteDatabase creates a connection."""
        db = SqliteDatabase(db_path=Path(":memory:"))
        db.initialize()
        assert db.connection is not None
        assert isinstance(db.connection, sqlite3.Connection)

    def test_initialize_creates_tables(self, memory_db):
        """Test that initialize creates all expected tables."""
        tables = _get_table_names(memory_db)
        assert {"account", "security", "price", "transaction"}.issubset(tables)

    def test_initialize_is_idempotent(self, memory_db: SqliteDatabase):
        """Test that initialize can be called multiple times safely."""
        tables_before = _get_table_names(memory_db)
        memory_db.initialize()
        tables_after = _get_table_names(memory_db)
        assert tables_before == tables_after

    def test_table_schemas_correct(self, memory_db):
        """Test that created tables have correct schema."""
        assert {"id", "name", "institution"}.issubset(
            _get_column_names(memory_db, "account")
        )
        assert {"key", "name", "type", "category"}.issubset(
            _get_column_names(memory_db, "security")
        )
        assert {"security_key", "date", "open", "high", "low", "close"}.issubset(
            _get_column_names(memory_db, "price")
        )
        assert {
            "id",
            "transaction_date",
            "type",
            "description",
            "amount",
            "units",
            "security_key",
            "account_id",
        }.issubset(_get_column_names(memory_db, '"transaction"'))

    def test_row_factory_set(self, memory_db):
        """Test that row_factory is set to sqlite3.Row."""
        assert memory_db.connection.row_factory is sqlite3.Row


class TestSqlitePragma:
    """Test SQLite PRAGMA and custom function setup."""

    def test_foreign_keys_enabled(self, memory_db):
        """Test that foreign key constraints are enabled."""
        result = memory_db.connection.execute("PRAGMA foreign_keys").fetchone()
        assert result[0] == 1

    def test_iregexp_available(self, memory_db):
        """Test that iregexp function is registered and available."""
        result = memory_db.connection.execute(
            "SELECT iregexp(?, ?)", ("test", "TEST")
        ).fetchone()
        assert result[0] == 1

    def test_foreign_key_constraint_enforced(self, memory_db):
        """Test that foreign key violation raises an error."""
        with pytest.raises(IntegrityError):
            with memory_db.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO price (security_key, date, open, high, low, close, properties) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    ("NONEXISTENT", "2024-01-01", 100, 100, 100, 100, "{}"),
                )


class TestCursorContextManager:
    """Test cursor context manager behavior."""

    def test_cursor_commits_on_success(self, memory_db):
        """Test that cursor context manager allows commits."""
        with memory_db.cursor() as cursor:
            cursor.execute(
                "INSERT INTO account (name, institution, properties) VALUES (?, ?, ?)",
                ("Test", "Bank", "{}"),
            )
            cursor.connection.commit()

        result = memory_db.connection.execute("SELECT name FROM account").fetchone()
        assert result[0] == "Test"

    def test_cursor_wraps_integrity_error(self, memory_db):
        """Test that IntegrityError is raised for constraint violations."""
        with memory_db.cursor() as cursor:
            cursor.execute(
                "INSERT INTO account (name, institution, properties) VALUES (?, ?, ?)",
                ("Test", "Bank", "{}"),
            )
            cursor.connection.commit()

        with pytest.raises(IntegrityError):
            with memory_db.cursor() as cursor:
                cursor.execute(
                    "INSERT INTO account (name, institution, properties) VALUES (?, ?, ?)",
                    ("Test", "Bank", "{}"),
                )

    def test_cursor_wraps_database_error(self, memory_db):
        """Test that DatabaseError is raised for general SQL errors."""
        with pytest.raises(DatabaseError):
            with memory_db.cursor() as cursor:
                cursor.execute("SELECT * FROM nonexistent_table")


class TestMigrations:
    """Tests for database migration support."""

    def test_migration_table_created(self, memory_db):
        """Test that the migration tracking table is created."""
        tables = _get_table_names(memory_db)
        assert "migration" in tables

    def test_migrations_are_idempotent(self):
        """Test that initializing twice is safe."""
        db = SqliteDatabase(db_path=Path(":memory:"))
        db.initialize()
        db.initialize()
        tables = _get_table_names(db)
        assert {"account", "security", "price", "transaction"}.issubset(tables)

    def test_migrations_create_schema_from_scratch(self):
        """Test that migrations can create the full schema on an empty database."""
        db = SqliteDatabase(db_path=Path(":memory:"))
        db.initialize()
        tables = _get_table_names(db)
        assert {"account", "security", "price", "transaction"}.issubset(tables)

    def test_all_migrations_recorded(self, memory_db):
        """Test that all migrations are recorded in the migration table."""
        migrations_path = (
            Path(__file__).parents[3]
            / "niveshpy"
            / "infrastructure"
            / "sqlite"
            / "migrations"
        )
        results = memory_db.connection.execute("SELECT file FROM migration").fetchall()
        recorded = {row[0] for row in results}
        expected_migrations = {f.name for f in migrations_path.glob("*.sql")}
        assert expected_migrations == recorded
