"""Tests for SqliteDatabase setup and connection management."""

import re
from pathlib import Path

import pytest
from sqlalchemy import inspect, select, text
from sqlalchemy.orm import Session

from niveshpy.infrastructure.sqlite.models import Account, Price, Security
from niveshpy.infrastructure.sqlite.sqlite_db import SqliteDatabase, _iregexp
from niveshpy.models.security import SecurityCategory, SecurityType

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
        with sql_db.session_factory() as session:
            result = session.execute(
                text("SELECT iregexp(:pattern, :value)"),
                params={"pattern": "test", "value": "TEST"},
            ).first()
            assert result[0] == 1

    def test_iregexp_in_where_clause(self, sql_db):
        """Test that iregexp works in SQL WHERE clause."""
        with sql_db.session_factory() as session:
            sec1 = Security(
                key="TEST1",
                name="Test Security One",
                type=SecurityType.STOCK,
                category=SecurityCategory.EQUITY,
                properties={},
            )
            sec2 = Security(
                key="TEST2",
                name="Another Security",
                type=SecurityType.STOCK,
                category=SecurityCategory.EQUITY,
                properties={},
            )
            session.add_all([sec1, sec2])
            session.commit()

            results = session.execute(
                text("SELECT * FROM security WHERE iregexp(:pattern, name)"),
                params={"pattern": "test"},
            ).all()

            assert len(results) == 1
            assert results[0][0] == "TEST1"

    def test_iregexp_case_insensitive_in_sql(self, sql_db):
        """Test case-insensitive matching in SQL queries."""
        with sql_db.session_factory() as session:
            acc1 = Account(name="Savings Account", institution="Bank A", properties={})
            acc2 = Account(name="checking account", institution="Bank B", properties={})
            acc3 = Account(
                name="INVESTMENT ACCOUNT", institution="Bank C", properties={}
            )
            session.add_all([acc1, acc2, acc3])
            session.commit()

            result = session.execute(
                text("SELECT name FROM account WHERE iregexp(:pattern, name)"),
                params={"pattern": "savings"},
            ).all()

            assert len(result) == 1
            assert result[0][0] == "Savings Account"


# ---------------------------------------------------------------------------
# SqliteDatabase
# ---------------------------------------------------------------------------


@pytest.fixture
def memory_db():
    """Create an in-memory SqliteDatabase."""
    db = SqliteDatabase(db_path=Path(":memory:"))
    db.initialize()
    return db


# ---------------------------------------------------------------------------
# SqliteDatabase
# ---------------------------------------------------------------------------


class TestSqliteDatabase:
    """Tests for SqliteDatabase initialization and setup."""

    def test_creates_db_directory(self, tmp_path):
        """Test that SqliteDatabase creates the parent directory."""
        db_path = tmp_path / "subdir" / "niveshpy.db"
        SqliteDatabase(db_path=db_path)
        assert db_path.parent.exists()

    def test_creates_engine(self):
        """Test that SqliteDatabase creates an engine."""
        db = SqliteDatabase(db_path=Path(":memory:"))
        assert db._engine is not None

    def test_initialize_creates_tables(self, memory_db):
        """Test that initialize creates all expected tables."""
        inspector = inspect(memory_db._engine)
        tables = set(inspector.get_table_names())
        assert {"account", "security", "price", "transaction"}.issubset(tables)

    def test_initialize_creates_session_factory(self, memory_db):
        """Test that initialize sets up the session factory."""
        assert memory_db.session_factory is not None

    def test_session_factory_creates_sessions(self, memory_db):
        """Test that session factory produces valid sessions."""
        with memory_db.session_factory() as session:
            assert isinstance(session, Session)

    def test_initialize_is_idempotent(self, memory_db: SqliteDatabase):
        """Test that initialize can be called multiple times safely."""
        inspector = inspect(memory_db._engine)
        tables_before = set(inspector.get_table_names())

        memory_db.initialize()

        tables_after = set(inspector.get_table_names())
        assert tables_before == tables_after

    def test_table_schemas_correct(self, memory_db):
        """Test that created tables have correct schema."""
        inspector = inspect(memory_db._engine)

        account_columns = {col["name"] for col in inspector.get_columns("account")}
        assert {"id", "name", "institution"}.issubset(account_columns)

        security_columns = {col["name"] for col in inspector.get_columns("security")}
        assert {"key", "name", "type", "category"}.issubset(security_columns)

        price_columns = {col["name"] for col in inspector.get_columns("price")}
        assert {"security_key", "date", "open", "high", "low", "close"}.issubset(
            price_columns
        )

        transaction_columns = {
            col["name"] for col in inspector.get_columns("transaction")
        }
        assert {
            "id",
            "transaction_date",
            "type",
            "description",
            "amount",
            "units",
            "security_key",
            "account_id",
        }.issubset(transaction_columns)


class TestSqlitePragma:
    """Test SQLite PRAGMA and custom function setup."""

    def test_foreign_keys_enabled(self, memory_db):
        """Test that foreign key constraints are enabled."""
        with memory_db.session_factory() as session:
            result = session.execute(text("PRAGMA foreign_keys")).first()
            assert result[0] == 1

    def test_iregexp_available(self, memory_db):
        """Test that iregexp function is registered and available."""
        with memory_db.session_factory() as session:
            result = session.execute(
                text("SELECT iregexp(:pattern, :value)"),
                params={"pattern": "test", "value": "TEST"},
            ).first()
            assert result[0] == 1

    def test_foreign_key_constraint_enforced(self, memory_db):
        """Test that foreign key violation raises an error."""
        from datetime import date
        from decimal import Decimal

        with memory_db.session_factory() as session:
            security = Security(
                key="TEST",
                name="Test Security",
                type=SecurityType.STOCK,
                category=SecurityCategory.EQUITY,
                properties={},
            )
            session.add(security)
            session.commit()

            price = Price(
                security_key="NONEXISTENT",
                date=date(2024, 1, 1),
                open=Decimal("100.0000"),
                high=Decimal("100.0000"),
                low=Decimal("100.0000"),
                close=Decimal("100.0000"),
                properties={},
            )
            session.add(price)

            with pytest.raises(Exception) as exc_info:
                session.commit()
            assert "FOREIGN KEY constraint failed" in str(exc_info.value)


class TestSqliteSessions:
    """Test session behavior."""

    def test_multiple_sessions_independent(self, memory_db):
        """Test that multiple sessions are independent."""
        with memory_db.session_factory() as session1:
            account = Account(name="Test 1", institution="Bank 1", properties={})
            session1.add(account)

            with memory_db.session_factory() as session2:
                accounts = session2.execute(select(Account)).scalars().all()
                assert len(accounts) == 0

            session1.commit()

            with memory_db.session_factory() as session2:
                accounts = session2.execute(select(Account)).scalars().all()
                assert len(accounts) == 1

    def test_session_context_manager(self, memory_db):
        """Test that session context manager cleans up properly."""
        with memory_db.session_factory() as session:
            account = Account(name="Cleanup Test", institution="Bank", properties={})
            session.add(account)
            session.commit()
            account_id = account.id

        with memory_db.session_factory() as session:
            result = session.get(Account, account_id)
            assert result is not None
            assert result.name == "Cleanup Test"


class TestMigrations:
    """Tests for database migration support."""

    def test_migration_table_created(self, memory_db):
        """Test that the migration tracking table is created."""
        inspector = inspect(memory_db._engine)
        tables = inspector.get_table_names()
        assert "migration" in tables

    def test_migrations_are_idempotent(self):
        """Test that initializing twice is safe."""
        db = SqliteDatabase(db_path=Path(":memory:"))
        db.initialize()
        db.initialize()

        inspector = inspect(db._engine)
        tables = set(inspector.get_table_names())
        assert {"account", "security", "price", "transaction"}.issubset(tables)

    def test_migrations_create_schema_from_scratch(self):
        """Test that migrations can create the full schema on an empty database."""
        db = SqliteDatabase(db_path=Path(":memory:"))
        db.initialize()

        inspector = inspect(db._engine)
        tables = set(inspector.get_table_names())
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
        with memory_db.session_factory() as session:
            result = session.execute(text("SELECT file FROM migration")).scalars().all()
            expected_migrations = {f.name for f in migrations_path.glob("*.sql")}
            assert expected_migrations == set(result)
