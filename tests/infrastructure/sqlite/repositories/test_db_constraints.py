"""DB-level constraint integration tests for SQLite repositories.

This module tests database schema constraints at the SQLite level, ensuring:
- Unique constraints are enforced at the DB layer
- Foreign key relationships are properly enforced
- CHECK constraints validate enum values
- Decimal precision is preserved during round-trip storage and retrieval
"""

from decimal import Decimal

import pytest

from niveshpy.exceptions import DatabaseError, IntegrityError
from niveshpy.models.security import SecurityCategory, SecurityType
from niveshpy.models.transaction import TransactionType

# ============================================================================
# FIXTURES (function scope for isolation)
# ============================================================================


@pytest.fixture(scope="function")
def seeded_security(db):
    """Insert a test security and return its key using raw SQL."""
    with db.cursor() as cursor:
        cursor.execute(
            'INSERT INTO security ("key", name, type, category, properties) '
            "VALUES (?, ?, ?, ?, ?)",
            ("INF123", "Infrastructure Fund", "mutual_fund", "equity", "{}"),
        )
    return "INF123"


@pytest.fixture(scope="function")
def seeded_account(db):
    """Insert a test account and return its ID using raw SQL."""
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO account (name, institution, properties) VALUES (?, ?, ?)",
            ("Primary", "HDFC", "{}"),
        )
        result = cursor.execute("SELECT last_insert_rowid()")
        account_id = result.fetchone()[0]
    return account_id


# ============================================================================
# GROUP 1: UNIQUE CONSTRAINTS (5 tests)
# ============================================================================
# These tests use db.cursor() directly because repositories use INSERT OR IGNORE.


def test_account_unique_constraint_enforced_at_db_level(db):
    """Raw DB cursor raises IntegrityError for duplicate (name, institution)."""
    # Insert first account row via cursor
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO account (name, institution, properties) VALUES (?, ?, ?)",
            ("Primary", "HDFC", "{}"),
        )

    # Attempt to insert identical row
    with pytest.raises(IntegrityError):
        with db.cursor() as cursor:
            cursor.execute(
                "INSERT INTO account (name, institution, properties) VALUES (?, ?, ?)",
                ("Primary", "HDFC", "{}"),
            )


def test_security_pk_enforced_at_db_level(db):
    """Raw DB cursor raises IntegrityError when inserting duplicate security key."""
    # Insert first security row via cursor
    with db.cursor() as cursor:
        cursor.execute(
            'INSERT INTO security ("key", name, type, category, properties) '
            "VALUES (?, ?, ?, ?, ?)",
            ("INF123", "Infrastructure Fund", "mutual_fund", "equity", "{}"),
        )

    # Attempt to insert same key
    with pytest.raises(IntegrityError):
        with db.cursor() as cursor:
            cursor.execute(
                'INSERT INTO security ("key", name, type, category, properties) '
                "VALUES (?, ?, ?, ?, ?)",
                ("INF123", "Duplicate Fund", "bond", "debt", "{}"),
            )


def test_price_pk_enforced_at_db_level(db, seeded_security):
    """Raw DB cursor raises IntegrityError for duplicate (security_key, date)."""
    # Insert first price row via cursor
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO price (security_key, date, open, high, low, close, properties) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                seeded_security,
                "2024-01-01",
                "150.00",
                "155.00",
                "149.00",
                "154.00",
                "{}",
            ),
        )

    # Attempt to insert same (security_key, date)
    with pytest.raises(IntegrityError):
        with db.cursor() as cursor:
            cursor.execute(
                "INSERT INTO price (security_key, date, open, high, low, close, properties) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    seeded_security,
                    "2024-01-01",
                    "151.00",
                    "156.00",
                    "150.00",
                    "155.00",
                    "{}",
                ),
            )


def test_account_composite_key_allows_same_name_different_institution(db):
    """Account unique constraint (name, institution) allows same name with different institution."""
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO account (name, institution, properties) VALUES (?, ?, ?)",
            ("Primary", "HDFC", "{}"),
        )
        cursor.execute(
            "INSERT INTO account (name, institution, properties) VALUES (?, ?, ?)",
            ("Primary", "ICICI", "{}"),
        )

    # Read back and verify both exist
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT name, institution FROM account WHERE name = ? ORDER BY institution",
            ("Primary",),
        )
        results = cursor.fetchall()

    assert len(results) == 2
    assert tuple(results[0]) == ("Primary", "HDFC")
    assert tuple(results[1]) == ("Primary", "ICICI")


def test_account_composite_key_allows_same_institution_different_name(db):
    """Account unique constraint (name, institution) allows same institution with different name."""
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO account (name, institution, properties) VALUES (?, ?, ?)",
            ("Alpha", "HDFC", "{}"),
        )
        cursor.execute(
            "INSERT INTO account (name, institution, properties) VALUES (?, ?, ?)",
            ("Beta", "HDFC", "{}"),
        )

    # Read back and verify both exist
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT name, institution FROM account WHERE institution = ? ORDER BY name",
            ("HDFC",),
        )
        results = cursor.fetchall()

    assert len(results) == 2
    assert tuple(results[0]) == ("Alpha", "HDFC")
    assert tuple(results[1]) == ("Beta", "HDFC")


# ============================================================================
# GROUP 2: FOREIGN KEY ENFORCEMENT (5 tests)
# ============================================================================


def test_delete_security_with_dependent_price_raises_integrity_error(
    db, seeded_security
):
    """Deleting a security that has prices raises IntegrityError due to FK constraint."""
    # Insert a price for the seeded security using raw SQL
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO price (security_key, date, open, high, low, close, properties) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                seeded_security,
                "2024-01-01",
                "150.00",
                "155.00",
                "149.00",
                "154.00",
                "{}",
            ),
        )

    # Attempt to delete the security using raw SQL
    with pytest.raises(IntegrityError):
        with db.cursor() as cursor:
            cursor.execute('DELETE FROM security WHERE "key" = ?', (seeded_security,))


def test_delete_security_with_dependent_transaction_raises_integrity_error(
    db, seeded_security, seeded_account
):
    """Deleting a security that has transactions raises IntegrityError due to FK constraint."""
    # Insert a transaction referencing the seeded security using raw SQL
    with db.cursor() as cursor:
        cursor.execute(
            'INSERT INTO "transaction" '
            "(transaction_date, type, description, amount, units, security_key, account_id, properties) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "2024-01-01",
                "purchase",
                "Test purchase",
                "1000",
                "100",
                seeded_security,
                seeded_account,
                "{}",
            ),
        )

    # Attempt to delete the security using raw SQL
    with pytest.raises(IntegrityError):
        with db.cursor() as cursor:
            cursor.execute('DELETE FROM security WHERE "key" = ?', (seeded_security,))


def test_delete_account_with_dependent_transaction_raises_integrity_error(
    db, seeded_account, seeded_security
):
    """Deleting an account that has transactions raises IntegrityError due to FK constraint."""
    # Insert a transaction referencing the seeded account using raw SQL
    with db.cursor() as cursor:
        cursor.execute(
            'INSERT INTO "transaction" '
            "(transaction_date, type, description, amount, units, security_key, account_id, properties) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "2024-01-01",
                "purchase",
                "Test purchase",
                "1000",
                "100",
                seeded_security,
                seeded_account,
                "{}",
            ),
        )

    # Attempt to delete the account using raw SQL
    with pytest.raises(IntegrityError):
        with db.cursor() as cursor:
            cursor.execute("DELETE FROM account WHERE id = ?", (seeded_account,))


def test_insert_transaction_with_nonexistent_security_key_raises_database_error(
    db, seeded_account
):
    """Inserting a transaction with a non-existent security_key raises DatabaseError."""
    with pytest.raises(DatabaseError):
        with db.cursor() as cursor:
            cursor.execute(
                'INSERT INTO "transaction" '
                "(transaction_date, type, description, amount, units, security_key, account_id, properties) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "2024-01-01",
                    "purchase",
                    "Test",
                    "1000",
                    "100",
                    "GHOST_KEY",
                    seeded_account,
                    "{}",
                ),
            )


def test_insert_transaction_with_nonexistent_account_id_raises_database_error(
    db, seeded_security
):
    """Inserting a transaction with a non-existent account_id raises DatabaseError."""
    with pytest.raises(DatabaseError):
        with db.cursor() as cursor:
            cursor.execute(
                'INSERT INTO "transaction" '
                "(transaction_date, type, description, amount, units, security_key, account_id, properties) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "2024-01-01",
                    "purchase",
                    "Test",
                    "1000",
                    "100",
                    seeded_security,
                    9999,
                    "{}",
                ),
            )


# ============================================================================
# GROUP 3: ENUM PERSISTENCE (6 tests)
# ============================================================================


def test_all_security_types_round_trip_as_python_enums(db):
    """All SecurityType enum values persist and round-trip correctly."""
    security_types = [
        ("stock", SecurityType.STOCK),
        ("bond", SecurityType.BOND),
        ("etf", SecurityType.ETF),
        ("mutual_fund", SecurityType.MUTUAL_FUND),
        ("other", SecurityType.OTHER),
    ]

    for i, (type_str, _sec_type) in enumerate(security_types):
        with db.cursor() as cursor:
            cursor.execute(
                'INSERT INTO security ("key", name, type, category, properties) '
                "VALUES (?, ?, ?, ?, ?)",
                (f"SEC_{i}", f"Security {i}", type_str, "equity", "{}"),
            )

    # Read back and verify
    with db.cursor() as cursor:
        cursor.execute('SELECT "key", type FROM security ORDER BY "key"')
        results = cursor.fetchall()

    assert len(results) == 5
    for i, (type_str, sec_type) in enumerate(security_types):
        key, stored_type = results[i]
        assert key == f"SEC_{i}"
        assert stored_type == type_str
        # Verify the model layer converts it to the enum
        assert SecurityType(stored_type) is sec_type


def test_all_security_categories_round_trip_as_python_enums(db):
    """All SecurityCategory enum values persist and round-trip correctly."""
    categories = [
        ("equity", SecurityCategory.EQUITY),
        ("debt", SecurityCategory.DEBT),
        ("commodity", SecurityCategory.COMMODITY),
        ("real_estate", SecurityCategory.REAL_ESTATE),
        ("other", SecurityCategory.OTHER),
    ]

    for i, (cat_str, _cat) in enumerate(categories):
        with db.cursor() as cursor:
            cursor.execute(
                'INSERT INTO security ("key", name, type, category, properties) '
                "VALUES (?, ?, ?, ?, ?)",
                (f"CAT_{i}", f"Category {i}", "stock", cat_str, "{}"),
            )

    # Read back and verify
    with db.cursor() as cursor:
        cursor.execute('SELECT "key", category FROM security ORDER BY "key"')
        results = cursor.fetchall()

    assert len(results) == 5
    for i, (cat_str, cat) in enumerate(categories):
        key, stored_cat = results[i]
        assert key == f"CAT_{i}"
        assert stored_cat == cat_str
        # Verify the model layer converts it to the enum
        assert SecurityCategory(stored_cat) is cat


def test_all_transaction_types_round_trip_as_python_enums(
    db, seeded_account, seeded_security
):
    """All TransactionType enum values persist and round-trip correctly."""
    transaction_types = [
        ("purchase", TransactionType.PURCHASE),
        ("sale", TransactionType.SALE),
    ]

    for i, (type_str, _txn_type) in enumerate(transaction_types):
        with db.cursor() as cursor:
            cursor.execute(
                'INSERT INTO "transaction" '
                "(transaction_date, type, description, amount, units, security_key, account_id, properties) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    f"2024-01-0{i + 1}",
                    type_str,
                    f"Transaction {i}",
                    "1000",
                    "100",
                    seeded_security,
                    seeded_account,
                    "{}",
                ),
            )

    # Read back and verify
    with db.cursor() as cursor:
        cursor.execute('SELECT type FROM "transaction" ORDER BY id')
        results = cursor.fetchall()

    assert len(results) == 2
    for i, (type_str, txn_type) in enumerate(transaction_types):
        stored_type = results[i][0]
        assert stored_type == type_str
        # Verify the model layer converts it to the enum
        assert TransactionType(stored_type) is txn_type


@pytest.mark.parametrize(
    "invalid_type",
    ["EQUITY", "invalid", "", "unknown_type"],
)
def test_check_constraint_rejects_invalid_security_type(db, invalid_type):
    """CHECK constraint rejects invalid security type values."""
    with pytest.raises(IntegrityError):
        with db.cursor() as cursor:
            cursor.execute(
                'INSERT INTO security ("key", name, type, category, properties) '
                "VALUES (?, ?, ?, ?, ?)",
                ("SEC_TEST", "Test", invalid_type, "equity", "{}"),
            )


@pytest.mark.parametrize(
    "invalid_category",
    ["EQUITY", "invalid", "", "unknown_category"],
)
def test_check_constraint_rejects_invalid_security_category(db, invalid_category):
    """CHECK constraint rejects invalid security category values."""
    with pytest.raises(IntegrityError):
        with db.cursor() as cursor:
            cursor.execute(
                'INSERT INTO security ("key", name, type, category, properties) '
                "VALUES (?, ?, ?, ?, ?)",
                ("SEC_TEST", "Test", "stock", invalid_category, "{}"),
            )


@pytest.mark.parametrize(
    "invalid_type",
    ["PURCHASE", "refund", "", "unknown_type"],
)
def test_check_constraint_rejects_invalid_transaction_type(
    db, seeded_account, seeded_security, invalid_type
):
    """CHECK constraint rejects invalid transaction type values."""
    with pytest.raises(IntegrityError):
        with db.cursor() as cursor:
            cursor.execute(
                'INSERT INTO "transaction" '
                "(transaction_date, type, description, amount, units, security_key, account_id, properties) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    "2024-01-01",
                    invalid_type,
                    "Test",
                    "1000",
                    "100",
                    seeded_security,
                    seeded_account,
                    "{}",
                ),
            )


# ============================================================================
# GROUP 4: DECIMAL PRECISION (5 tests)
# ============================================================================


def test_price_ohlc_columns_preserve_4_decimal_places(db, seeded_security):
    """Price OHLC columns preserve 4 decimal places during round-trip."""
    original_open = "150.1234"
    original_high = "155.0001"
    original_low = "149.9999"
    original_close = "154.5678"

    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO price (security_key, date, open, high, low, close, properties) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                seeded_security,
                "2024-01-01",
                original_open,
                original_high,
                original_low,
                original_close,
                "{}",
            ),
        )

    # Read back and verify
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT open, high, low, close FROM price WHERE security_key = ?",
            (seeded_security,),
        )
        stored_open, stored_high, stored_low, stored_close = cursor.fetchone()

    assert Decimal(str(stored_open)) == Decimal(original_open)
    assert Decimal(str(stored_high)) == Decimal(original_high)
    assert Decimal(str(stored_low)) == Decimal(original_low)
    assert Decimal(str(stored_close)) == Decimal(original_close)

    # Also verify string representation
    assert str(Decimal(str(stored_open))) == original_open
    assert str(Decimal(str(stored_high))) == original_high
    assert str(Decimal(str(stored_low))) == original_low
    assert str(Decimal(str(stored_close))) == original_close


def test_transaction_amount_preserves_2_decimal_places(
    db, seeded_account, seeded_security
):
    """Transaction amount column preserves 2 decimal places during round-trip."""
    original_amount = "12345.67"

    with db.cursor() as cursor:
        cursor.execute(
            'INSERT INTO "transaction" '
            "(transaction_date, type, description, amount, units, security_key, account_id, properties) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "2024-01-01",
                "purchase",
                "Test",
                original_amount,
                "100",
                seeded_security,
                seeded_account,
                "{}",
            ),
        )

    # Read back and verify
    with db.cursor() as cursor:
        cursor.execute(
            'SELECT amount FROM "transaction" WHERE description = ?', ("Test",)
        )
        stored_amount = cursor.fetchone()[0]

    assert Decimal(str(stored_amount)) == Decimal(original_amount)
    assert str(Decimal(str(stored_amount))) == original_amount


def test_transaction_units_preserve_3_decimal_places(
    db, seeded_account, seeded_security
):
    """Transaction units column preserves 3 decimal places during round-trip."""
    original_units = "100.123"

    with db.cursor() as cursor:
        cursor.execute(
            'INSERT INTO "transaction" '
            "(transaction_date, type, description, amount, units, security_key, account_id, properties) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "2024-01-01",
                "purchase",
                "Test",
                "1000",
                original_units,
                seeded_security,
                seeded_account,
                "{}",
            ),
        )

    # Read back and verify
    with db.cursor() as cursor:
        cursor.execute(
            'SELECT units FROM "transaction" WHERE description = ?', ("Test",)
        )
        stored_units = cursor.fetchone()[0]

    assert Decimal(str(stored_units)) == Decimal(original_units)
    assert str(Decimal(str(stored_units))) == original_units


def test_large_decimal_value_survives_roundtrip(db):
    """Large decimal values survive round-trip, within NUMERIC(24,4) precision."""
    # First create the security using raw SQL
    with db.cursor() as cursor:
        cursor.execute(
            'INSERT INTO security ("key", name, type, category, properties) '
            "VALUES (?, ?, ?, ?, ?)",
            ("LARGE", "Large Value Test", "stock", "equity", "{}"),
        )

    # Use a large but precision-preserving value: 12 digits before decimal
    large_value = "123456789012.3456"

    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO price (security_key, date, open, high, low, close, properties) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "LARGE",
                "2024-01-01",
                large_value,
                large_value,
                large_value,
                large_value,
                "{}",
            ),
        )

    # Read back and verify
    with db.cursor() as cursor:
        cursor.execute(
            "SELECT open, high, low, close FROM price WHERE security_key = ?",
            ("LARGE",),
        )
        stored_open, stored_high, stored_low, stored_close = cursor.fetchone()

    assert Decimal(str(stored_open)) == Decimal(large_value)
    assert Decimal(str(stored_high)) == Decimal(large_value)
    assert Decimal(str(stored_low)) == Decimal(large_value)
    assert Decimal(str(stored_close)) == Decimal(large_value)
    assert isinstance(Decimal(str(stored_open)), Decimal)


def test_minimum_precision_boundary_values_preserved(db):
    """Minimum precision boundary values are preserved (0.0001 for price, 0.01 for amount, 0.001 for units)."""
    # Create security and account using raw SQL
    with db.cursor() as cursor:
        cursor.execute(
            'INSERT INTO security ("key", name, type, category, properties) '
            "VALUES (?, ?, ?, ?, ?)",
            ("MIN_PRICE", "Min Price Test", "stock", "equity", "{}"),
        )
        cursor.execute(
            "INSERT INTO account (name, institution, properties) VALUES (?, ?, ?)",
            ("Test Account", "Test Bank", "{}"),
        )
        result = cursor.execute("SELECT last_insert_rowid()")
        account_id = result.fetchone()[0]

    # Test minimum price precision (4 decimal places)
    min_price = "0.0001"
    with db.cursor() as cursor:
        cursor.execute(
            "INSERT INTO price (security_key, date, open, high, low, close, properties) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                "MIN_PRICE",
                "2024-01-01",
                min_price,
                min_price,
                min_price,
                min_price,
                "{}",
            ),
        )
        cursor.execute("SELECT open FROM price WHERE security_key = ?", ("MIN_PRICE",))
        stored_price = cursor.fetchone()[0]

    assert Decimal(str(stored_price)) == Decimal(min_price)

    # Test minimum amount precision (2 decimal places)
    min_amount = "0.01"
    with db.cursor() as cursor:
        cursor.execute(
            'INSERT INTO "transaction" '
            "(transaction_date, type, description, amount, units, security_key, account_id, properties) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "2024-01-01",
                "purchase",
                "Min Amount",
                min_amount,
                "1.000",
                "MIN_PRICE",
                account_id,
                "{}",
            ),
        )
        cursor.execute(
            'SELECT amount FROM "transaction" WHERE description = ?', ("Min Amount",)
        )
        stored_amount = cursor.fetchone()[0]

    assert Decimal(str(stored_amount)) == Decimal(min_amount)

    # Test minimum units precision (3 decimal places)
    min_units = "0.001"
    with db.cursor() as cursor:
        cursor.execute(
            'INSERT INTO "transaction" '
            "(transaction_date, type, description, amount, units, security_key, account_id, properties) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "2024-01-02",
                "sale",
                "Min Units",
                "10.00",
                min_units,
                "MIN_PRICE",
                account_id,
                "{}",
            ),
        )
        cursor.execute(
            'SELECT units FROM "transaction" WHERE description = ?', ("Min Units",)
        )
        stored_units = cursor.fetchone()[0]

    assert Decimal(str(stored_units)) == Decimal(min_units)
