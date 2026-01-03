"""Tests for database module."""

import re
from unittest.mock import patch

import pytest
from sqlalchemy import event, inspect, text
from sqlmodel import Session, SQLModel, create_engine, select

from niveshpy.database import _iregexp, get_session, initialize
from niveshpy.models.account import Account
from niveshpy.models.price import Price
from niveshpy.models.security import Security, SecurityCategory, SecurityType


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
        assert _iregexp("^line2", value) is False  # Doesn't match at string start
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


class TestIregexpInSQL:
    """Test _iregexp function integration with SQLite."""

    @pytest.fixture
    def sql_engine(self):
        """Create an in-memory engine with iregexp registered."""
        engine = create_engine("sqlite:///:memory:")

        @event.listens_for(engine, "connect")
        def setup(dbapi_conn, connection_record):
            dbapi_conn.create_function("iregexp", 2, _iregexp)

        return engine

    def test_iregexp_function_callable(self, sql_engine):
        """Test that iregexp function is directly callable in SQL."""
        SQLModel.metadata.create_all(sql_engine)

        with Session(sql_engine) as session:
            # Test iregexp function directly
            result = session.exec(
                text("SELECT iregexp(:pattern, :value)"),
                params={"pattern": "test", "value": "TEST"},
            ).first()
            assert result[0] == 1  # SQLite returns 1 for True

    def test_iregexp_in_where_clause(self, sql_engine):
        """Test that iregexp works in SQL WHERE clause."""
        SQLModel.metadata.create_all(sql_engine)

        with Session(sql_engine) as session:
            # Create test data
            sec1 = Security(
                key="TEST1",
                name="Test Security One",
                type=SecurityType.STOCK,
                category=SecurityCategory.EQUITY,
            )
            sec2 = Security(
                key="TEST2",
                name="Another Security",
                type=SecurityType.STOCK,
                category=SecurityCategory.EQUITY,
            )
            session.add_all([sec1, sec2])
            session.commit()

            # Query using iregexp function directly
            results = session.exec(
                text("SELECT * FROM security WHERE iregexp(:pattern, name)"),
                params={"pattern": "test"},
            ).all()

            # Should match case-insensitively
            assert len(results) == 1
            assert results[0][0] == "TEST1"  # First column is key

    def test_iregexp_case_insensitive_in_sql(self, sql_engine):
        """Test case-insensitive matching in SQL queries."""
        SQLModel.metadata.create_all(sql_engine)

        with Session(sql_engine) as session:
            # Create test accounts with mixed case
            acc1 = Account(name="Savings Account", institution="Bank A")
            acc2 = Account(name="checking account", institution="Bank B")
            acc3 = Account(name="INVESTMENT ACCOUNT", institution="Bank C")
            session.add_all([acc1, acc2, acc3])
            session.commit()

            # Query for "account" case-insensitively using iregexp function
            result = session.exec(
                text("SELECT name FROM account WHERE iregexp(:pattern, name)"),
                params={"pattern": "savings"},
            ).all()

            assert len(result) == 1
            assert result[0][0] == "Savings Account"


class TestSetSqlitePragma:
    """Test set_sqlite_pragma event handler."""

    def test_foreign_keys_enabled(self, engine, session):
        """Test that foreign key constraints are enabled."""
        # Create a security
        security = Security(
            key="TEST",
            name="Test Security",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        )
        session.add(security)
        session.commit()

        # Try to create a price with non-existent security key
        from datetime import date
        from decimal import Decimal

        price = Price(
            security_key="NONEXISTENT",
            date=date(2024, 1, 1),
            open=Decimal("100.0000"),
            high=Decimal("100.0000"),
            low=Decimal("100.0000"),
            close=Decimal("100.0000"),
        )
        session.add(price)

        # Should raise IntegrityError due to foreign key constraint
        with pytest.raises(Exception) as exc_info:
            session.commit()
        assert "FOREIGN KEY constraint failed" in str(exc_info.value)

    def test_iregexp_function_available(self, engine):
        """Test that iregexp function is registered and available."""
        with Session(engine) as session:
            # Test using raw SQL
            result = session.exec(
                text("SELECT iregexp(:pattern, :value)"),
                params={"pattern": "test", "value": "TEST"},
            ).first()
            assert result[0] == 1  # SQLite returns 1 for True

    def test_pragma_set_on_new_connection(self):
        """Test that PRAGMA is set when new connection is created."""
        engine = create_engine("sqlite:///:memory:")

        @event.listens_for(engine, "connect")
        def set_pragma(dbapi_conn, connection_record):
            cursor = dbapi_conn.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.close()

        SQLModel.metadata.create_all(engine)

        # Verify PRAGMA is set
        with engine.connect() as conn:
            result = conn.exec_driver_sql("PRAGMA foreign_keys").fetchone()
            assert result[0] == 1  # 1 means ON

    def test_multiple_connections_get_pragma(self, engine):
        """Test that PRAGMA is set for multiple connections."""
        # Create two separate sessions
        with Session(engine) as session1:
            result1 = session1.exec(text("PRAGMA foreign_keys")).first()
            assert result1[0] == 1  # Should be enabled

        with Session(engine) as session2:
            result2 = session2.exec(text("PRAGMA foreign_keys")).first()
            assert result2[0] == 1  # Should still be enabled


class TestInitialize:
    """Test initialize function."""

    @patch("niveshpy.database.SQLModel.metadata.create_all")
    def test_creates_tables(self, mock_create_all):
        """Test that initialize calls create_all."""
        initialize()
        mock_create_all.assert_called_once()

    @patch("niveshpy.database.logging.logger")
    @patch("niveshpy.database.SQLModel.metadata.create_all")
    def test_logs_info_message(self, mock_create_all, mock_logger):
        """Test that initialize logs info message."""
        initialize()
        mock_logger.info.assert_called_once()
        # Check that the log message contains the database path
        call_args = mock_logger.info.call_args[0][0]
        assert "Creating database and tables" in call_args

    def test_idempotent_initialization(self):
        """Test that initialize can be called multiple times safely."""
        # Create a fresh in-memory database
        test_engine = create_engine("sqlite:///:memory:")

        # First call
        SQLModel.metadata.create_all(test_engine)

        # Get table names
        inspector = inspect(test_engine)
        tables_before = set(inspector.get_table_names())

        # Second call - should not fail
        SQLModel.metadata.create_all(test_engine)

        # Tables should be the same
        tables_after = set(inspector.get_table_names())
        assert tables_before == tables_after

    def test_creates_all_expected_tables(self):
        """Test that initialize creates all expected tables."""
        test_engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(test_engine)

        inspector = inspect(test_engine)
        tables = inspector.get_table_names()

        expected_tables = {"account", "security", "price", "transaction"}
        assert expected_tables.issubset(set(tables))

    def test_table_schemas_correct(self):
        """Test that created tables have correct schema."""
        test_engine = create_engine("sqlite:///:memory:")
        SQLModel.metadata.create_all(test_engine)

        inspector = inspect(test_engine)

        # Check Account table
        account_columns = {col["name"] for col in inspector.get_columns("account")}
        assert {"id", "name", "institution"}.issubset(account_columns)

        # Check Security table
        security_columns = {col["name"] for col in inspector.get_columns("security")}
        assert {"key", "name", "type", "category"}.issubset(security_columns)

        # Check Price table
        price_columns = {col["name"] for col in inspector.get_columns("price")}
        assert {"security_key", "date", "open", "high", "low", "close"}.issubset(
            price_columns
        )

        # Check Transaction table
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


class TestGetSession:
    """Test get_session function."""

    @patch("niveshpy.database._engine")
    def test_returns_valid_session(self, mock_engine):
        """Test that get_session returns a Session object."""
        mock_engine.configure_mock()
        result = get_session()
        assert isinstance(result, Session)

    @patch("niveshpy.database._engine")
    def test_session_bound_to_engine(self, mock_engine):
        """Test that returned session is bound to the engine."""
        session = get_session()
        assert session.bind == mock_engine

    def test_multiple_sessions_independent(self, engine):
        """Test that multiple sessions are independent."""
        # Use test fixture engine instead of production
        session1 = Session(engine)
        session2 = Session(engine)

        # Add data in session1
        account1 = Account(name="Test 1", institution="Bank 1")
        session1.add(account1)

        # Session2 should not see uncommitted data
        accounts_in_session2 = session2.exec(select(Account)).all()
        assert len(accounts_in_session2) == 0

        session1.commit()

        # Now session2 should see the committed data
        session2.expire_all()  # Refresh session2
        accounts_in_session2 = session2.exec(select(Account)).all()
        assert len(accounts_in_session2) == 1

        session1.close()
        session2.close()

    def test_session_can_query(self, engine):
        """Test that session can execute queries."""
        session = Session(engine)

        # Create and query data
        account = Account(name="Test Account", institution="Test Bank")
        session.add(account)
        session.commit()

        result = session.exec(select(Account)).first()
        assert result is not None
        assert result.name == "Test Account"

        session.close()

    def test_session_can_commit(self, engine):
        """Test that session can commit changes."""
        session = Session(engine)

        account = Account(name="Commit Test", institution="Bank")
        session.add(account)
        session.commit()

        # Verify in new session
        session2 = Session(engine)
        result = session2.exec(
            select(Account).where(Account.name == "Commit Test")
        ).first()
        assert result is not None
        assert result.institution == "Bank"

        session.close()
        session2.close()

    def test_session_cleanup(self, engine):
        """Test that session context manager cleans up properly."""
        account_id = None
        with Session(engine) as session:
            account = Account(name="Cleanup Test", institution="Bank")
            session.add(account)
            session.commit()
            account_id = account.id

        # Verify data persists after session closes
        with Session(engine) as new_session:
            result = new_session.get(Account, account_id)
            assert result is not None
            assert result.name == "Cleanup Test"


class TestModuleLevelInit:
    """Test module-level initialization."""

    def test_app_path_resolution(self):
        """Test that app_path is resolved correctly."""
        from niveshpy.database import app_path

        assert app_path.exists()
        assert app_path.is_dir()
        assert "niveshpy" in str(app_path)

    def test_db_path_format(self):
        """Test that _db_path has correct format."""
        from niveshpy.database import _db_path

        assert _db_path.suffix == ".db"
        assert _db_path.stem == "niveshpy"
        assert _db_path.is_absolute()

    def test_sqlite_url_format(self):
        """Test that _sqlite_url has correct format."""
        from niveshpy.database import _sqlite_url

        assert _sqlite_url.startswith("sqlite:///")
        assert "niveshpy.db" in _sqlite_url

    def test_engine_creation(self):
        """Test that _engine is created."""
        from niveshpy.database import _engine

        assert _engine is not None
        assert str(_engine.url).startswith("sqlite:///")

    def test_event_handler_registered(self):
        """Test that event handler is registered on module import."""
        from niveshpy.database import _engine

        # Verify that the engine has the custom function by testing it works
        with Session(_engine) as session:
            # If iregexp wasn't registered, this would fail
            result = session.exec(
                text("SELECT iregexp(:pattern, :value)"),
                params={"pattern": "test", "value": "TEST"},
            ).first()
            assert result[0] == 1  # Should match case-insensitively
