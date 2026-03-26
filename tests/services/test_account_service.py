"""Tests for AccountService."""

from collections.abc import Sequence
from unittest.mock import patch

import pytest

from niveshpy.exceptions import AmbiguousResourceError, InvalidInputError
from niveshpy.models.account import Account, AccountPublic
from niveshpy.services.account import AccountService
from niveshpy.services.result import InsertResult, MergeAction


@pytest.fixture
def account_service(session):
    """Create AccountService instance with patched get_session."""
    with patch("niveshpy.services.account.get_session") as mock_get_session:
        # Make get_session return a context manager that yields the test session
        mock_get_session.return_value.__enter__.return_value = session
        mock_get_session.return_value.__exit__.return_value = None
        yield AccountService()


@pytest.fixture
def sample_accounts(session):
    """Create sample accounts for testing."""
    accounts = [
        Account(name="HDFC Savings", institution="HDFC Bank"),
        Account(name="ICICI Current", institution="ICICI Bank"),
        Account(name="SBI Savings", institution="State Bank of India"),
        Account(name="HDFC Current", institution="HDFC Bank"),
        Account(name="Zerodha Demat", institution="Zerodha"),
    ]
    session.add_all(accounts)
    session.commit()
    for account in accounts:
        session.refresh(account)
    return accounts


class TestListAccounts:
    """Tests for list_accounts method."""

    def test_list_all_accounts_no_filter(self, account_service, sample_accounts):
        """Test listing all accounts without any filters."""
        accounts = account_service.list_accounts(queries=(), limit=30, offset=0)

        assert len(accounts) == 5
        assert all(isinstance(acc, AccountPublic) for acc in accounts)
        assert accounts[0].name == "HDFC Savings"

    def test_list_accounts_with_limit(self, account_service, sample_accounts):
        """Test listing accounts with limit."""
        accounts = account_service.list_accounts(queries=(), limit=3, offset=0)

        assert len(accounts) == 3

    def test_list_accounts_with_offset(self, account_service, sample_accounts):
        """Test listing accounts with offset."""
        accounts = account_service.list_accounts(queries=(), limit=30, offset=2)

        assert len(accounts) == 3
        assert accounts[0].name == "SBI Savings"

    def test_list_accounts_with_limit_and_offset(
        self, account_service, sample_accounts
    ):
        """Test listing accounts with both limit and offset."""
        accounts = account_service.list_accounts(queries=(), limit=2, offset=1)

        assert len(accounts) == 2
        assert accounts[0].name == "ICICI Current"

    def test_list_accounts_offset_beyond_total(self, account_service, sample_accounts):
        """Test listing accounts with offset beyond total count."""
        accounts = account_service.list_accounts(queries=(), limit=30, offset=10)

        assert len(accounts) == 0

    def test_list_accounts_with_query_filter(self, account_service, sample_accounts):
        """Test listing accounts with query filter."""
        accounts = account_service.list_accounts(queries=("HDFC",), limit=30, offset=0)

        assert len(accounts) == 2
        assert all("HDFC" in acc.name or "HDFC" in acc.institution for acc in accounts)

    def test_list_accounts_query_no_matches(self, account_service, sample_accounts):
        """Test listing accounts with query that has no matches."""
        accounts = account_service.list_accounts(
            queries=("NonExistent",), limit=30, offset=0
        )

        assert len(accounts) == 0

    def test_list_accounts_empty_database(self, account_service):
        """Test listing accounts when database is empty."""
        accounts = account_service.list_accounts(queries=(), limit=30, offset=0)

        assert len(accounts) == 0

    def test_list_accounts_invalid_limit_zero(self, account_service, sample_accounts):
        """Test that zero limit raises InvalidInputError."""
        with pytest.raises(InvalidInputError, match="Limit must be positive"):
            account_service.list_accounts(queries=(), limit=0, offset=0)

    def test_list_accounts_invalid_limit_negative(
        self, account_service, sample_accounts
    ):
        """Test that negative limit raises InvalidInputError."""
        with pytest.raises(InvalidInputError, match="Limit must be positive"):
            account_service.list_accounts(queries=(), limit=-1, offset=0)

    def test_list_accounts_invalid_offset_negative(
        self, account_service, sample_accounts
    ):
        """Test that negative offset raises InvalidInputError."""
        with pytest.raises(InvalidInputError, match="Offset cannot be negative"):
            account_service.list_accounts(queries=(), limit=30, offset=-1)

    def test_list_accounts_returns_accountpublic(
        self, account_service, sample_accounts
    ):
        """Test that list_accounts returns AccountPublic instances."""
        accounts = account_service.list_accounts(queries=(), limit=1, offset=0)

        assert len(accounts) == 1
        assert isinstance(accounts[0], AccountPublic)
        assert hasattr(accounts[0], "id")
        assert hasattr(accounts[0], "created_at")


class TestAddAccount:
    """Tests for add_account method."""

    def test_add_account_success(self, account_service, session):
        """Test successfully adding a new account."""
        result = account_service.add_account(
            name="Test Account", institution="Test Bank", source=None
        )

        assert isinstance(result, InsertResult)
        assert result.action == MergeAction.INSERT
        assert result.data.name == "Test Account"
        assert result.data.institution == "Test Bank"
        assert result.data.id is not None
        assert result.data.properties == {}

    def test_add_account_with_source(self, account_service, session):
        """Test adding account with source property."""
        result = account_service.add_account(
            name="Test Account", institution="Test Bank", source="CAS"
        )

        assert result.action == MergeAction.INSERT
        assert result.data.properties == {"source": "CAS"}

    def test_add_account_duplicate_returns_existing(self, account_service, session):
        """Test that adding duplicate account returns existing one."""
        # Add first account
        result1 = account_service.add_account(
            name="Duplicate Account", institution="Test Bank", source=None
        )
        account_id = result1.data.id

        # Try to add duplicate
        result2 = account_service.add_account(
            name="Duplicate Account", institution="Test Bank", source=None
        )

        assert result2.action == MergeAction.NOTHING
        assert result2.data.id == account_id
        assert result2.data.name == "Duplicate Account"

    def test_add_account_same_name_different_institution(
        self, account_service, session
    ):
        """Test adding accounts with same name but different institutions."""
        result1 = account_service.add_account(
            name="Savings", institution="HDFC Bank", source=None
        )
        result2 = account_service.add_account(
            name="Savings", institution="ICICI Bank", source=None
        )

        assert result1.action == MergeAction.INSERT
        assert result2.action == MergeAction.INSERT
        assert result1.data.id != result2.data.id

    def test_add_account_different_name_same_institution(
        self, account_service, session
    ):
        """Test adding accounts with different names but same institution."""
        result1 = account_service.add_account(
            name="Savings", institution="HDFC Bank", source=None
        )
        result2 = account_service.add_account(
            name="Current", institution="HDFC Bank", source=None
        )

        assert result1.action == MergeAction.INSERT
        assert result2.action == MergeAction.INSERT
        assert result1.data.id != result2.data.id

    def test_add_account_strips_whitespace(self, account_service, session):
        """Test that add_account strips whitespace from name and institution."""
        result = account_service.add_account(
            name="  Test Account  ", institution="  Test Bank  ", source=None
        )

        assert result.data.name == "Test Account"
        assert result.data.institution == "Test Bank"

    def test_add_account_empty_name_raises_error(self, account_service, session):
        """Test that empty name raises InvalidInputError."""
        with pytest.raises(
            InvalidInputError, match="Account name and institution cannot be empty"
        ):
            account_service.add_account(name="", institution="Test Bank", source=None)

    def test_add_account_whitespace_only_name_raises_error(
        self, account_service, session
    ):
        """Test that whitespace-only name raises InvalidInputError."""
        with pytest.raises(
            InvalidInputError, match="Account name and institution cannot be empty"
        ):
            account_service.add_account(
                name="   ", institution="Test Bank", source=None
            )

    def test_add_account_empty_institution_raises_error(self, account_service, session):
        """Test that empty institution raises InvalidInputError."""
        with pytest.raises(
            InvalidInputError, match="Account name and institution cannot be empty"
        ):
            account_service.add_account(
                name="Test Account", institution="", source=None
            )

    def test_add_account_whitespace_only_institution_raises_error(
        self, account_service, session
    ):
        """Test that whitespace-only institution raises InvalidInputError."""
        with pytest.raises(
            InvalidInputError, match="Account name and institution cannot be empty"
        ):
            account_service.add_account(
                name="Test Account", institution="   ", source=None
            )

    def test_add_account_both_empty_raises_error(self, account_service, session):
        """Test that both empty name and institution raises InvalidInputError."""
        with pytest.raises(
            InvalidInputError, match="Account name and institution cannot be empty"
        ):
            account_service.add_account(name="", institution="", source=None)

    def test_add_account_special_characters(self, account_service, session):
        """Test adding account with special characters."""
        result = account_service.add_account(
            name="Account #1 (Primary)", institution="Bank & Co.", source=None
        )

        assert result.action == MergeAction.INSERT
        assert result.data.name == "Account #1 (Primary)"
        assert result.data.institution == "Bank & Co."

    def test_add_account_unicode_characters(self, account_service, session):
        """Test adding account with unicode characters."""
        result = account_service.add_account(
            name="बचत खाता", institution="भारतीय स्टेट बैंक", source=None
        )

        assert result.action == MergeAction.INSERT
        assert result.data.name == "बचत खाता"
        assert result.data.institution == "भारतीय स्टेट बैंक"


class TestResolveAccountId:
    """Tests for resolve_account_id method."""

    def test_resolve_empty_queries_ambiguous_allowed(
        self, account_service: AccountService, sample_accounts: list[Account]
    ):
        """Test resolving with empty queries when ambiguous is allowed."""
        accounts: Sequence[AccountPublic] = account_service.resolve_account_id(
            queries=(), limit=10, allow_ambiguous=True
        )

        assert len(accounts) == 5
        assert all(isinstance(acc, AccountPublic) for acc in accounts)
        for i in range(5):
            assert accounts[i].id == sample_accounts[i].id

    def test_resolve_empty_queries_ambiguous_not_allowed(
        self, account_service: AccountService, sample_accounts: list[Account]
    ):
        """Test resolving with empty queries when ambiguous is not allowed."""
        with pytest.raises(InvalidInputError, match="No queries provided"):
            account_service.resolve_account_id(
                queries=(), limit=10, allow_ambiguous=False
            )

    def test_resolve_empty_queries_respects_limit(
        self, account_service: AccountService, sample_accounts: list[Account]
    ):
        """Test that empty queries resolution respects limit."""
        accounts: Sequence[AccountPublic] = account_service.resolve_account_id(
            queries=(), limit=3, allow_ambiguous=True
        )

        assert len(accounts) == 3

    def test_resolve_exact_match_by_id(
        self, account_service: AccountService, sample_accounts: list[Account]
    ):
        """Test resolving by exact account ID."""
        account_id = sample_accounts[0].id
        accounts: Sequence[AccountPublic] = account_service.resolve_account_id(
            queries=(str(account_id),), limit=10, allow_ambiguous=True
        )

        assert len(accounts) == 1
        assert accounts[0].id == account_id
        assert accounts[0].name == sample_accounts[0].name
        assert accounts[0].institution == sample_accounts[0].institution

    def test_resolve_exact_match_by_id_with_whitespace(
        self, account_service: AccountService, sample_accounts: list[Account]
    ):
        """Test resolving by ID with surrounding whitespace."""
        account_id = sample_accounts[0].id
        accounts: Sequence[AccountPublic] = account_service.resolve_account_id(
            queries=(f"  {account_id}  ",), limit=10, allow_ambiguous=True
        )

        assert len(accounts) == 1
        assert accounts[0].id == account_id

    def test_resolve_nonexistent_id_ambiguous_not_allowed(
        self, account_service: AccountService, sample_accounts: list[Account]
    ):
        """Test resolving non-existent ID when ambiguous not allowed."""
        with pytest.raises(AmbiguousResourceError, match="account"):
            account_service.resolve_account_id(
                queries=("99999",), limit=10, allow_ambiguous=False
            )

    def test_resolve_nonexistent_id_ambiguous_allowed(
        self, account_service: AccountService, sample_accounts: list[Account]
    ):
        """Test resolving non-existent ID when ambiguous allowed falls back to text search."""
        accounts: Sequence[AccountPublic] = account_service.resolve_account_id(
            queries=("99999",), limit=10, allow_ambiguous=True
        )

        # Should fall back to text search and find nothing
        assert len(accounts) == 0

    def test_resolve_text_search_no_matches(
        self, account_service: AccountService, sample_accounts: list[Account]
    ):
        """Test text search with no matches."""
        accounts: Sequence[AccountPublic] = account_service.resolve_account_id(
            queries=("NonExistent",), limit=10, allow_ambiguous=True
        )

        assert len(accounts) == 0

    def test_resolve_text_search_single_match(
        self, account_service: AccountService, sample_accounts: list[Account]
    ):
        """Test text search with exactly one match."""
        accounts: Sequence[AccountPublic] = account_service.resolve_account_id(
            queries=("Zerodha",), limit=10, allow_ambiguous=True
        )

        assert len(accounts) == 1
        assert accounts[0].name == "Zerodha Demat"

    def test_resolve_text_search_multiple_matches(
        self, account_service: AccountService, sample_accounts: list[Account]
    ):
        """Test text search with multiple matches."""
        accounts: Sequence[AccountPublic] = account_service.resolve_account_id(
            queries=("HDFC",), limit=10, allow_ambiguous=True
        )

        assert len(accounts) == 2
        assert all("HDFC" in acc.name or "HDFC" in acc.institution for acc in accounts)

    def test_resolve_text_search_multiple_matches_ambiguous_not_allowed(
        self, account_service: AccountService, sample_accounts: list[Account]
    ):
        """Test text search with multiple matches when ambiguous not allowed."""
        with pytest.raises(AmbiguousResourceError, match="account"):
            account_service.resolve_account_id(
                queries=("HDFC",), limit=10, allow_ambiguous=False
            )

    def test_resolve_text_search_respects_limit(
        self, account_service: AccountService, sample_accounts: list[Account]
    ):
        """Test that text search respects limit parameter."""
        accounts: Sequence[AccountPublic] = account_service.resolve_account_id(
            queries=("HDFC",), limit=1, allow_ambiguous=True
        )

        # Should find multiple HDFC accounts but limit to 1
        # With limit=1 and exactly 1 result, it should return EXACT
        assert len(accounts) == 1

    def test_resolve_non_numeric_query_ambiguous_not_allowed(
        self, account_service: AccountService, sample_accounts: list[Account]
    ):
        """Test non-numeric query when ambiguous not allowed."""
        with pytest.raises(AmbiguousResourceError, match="account"):
            account_service.resolve_account_id(
                queries=("HDFC",), limit=10, allow_ambiguous=False
            )

    def test_resolve_empty_database(self, account_service: AccountService):
        """Test resolving in empty database."""
        accounts: Sequence[AccountPublic] = account_service.resolve_account_id(
            queries=("test",), limit=10, allow_ambiguous=True
        )

        assert len(accounts) == 0

    def test_resolve_returns_accountpublic(
        self, account_service: AccountService, sample_accounts: list[Account]
    ):
        """Test that resolution returns AccountPublic instances."""
        account_id = sample_accounts[0].id
        accounts: Sequence[AccountPublic] = account_service.resolve_account_id(
            queries=(str(account_id),), limit=10, allow_ambiguous=True
        )

        assert isinstance(accounts[0], AccountPublic)
        assert hasattr(accounts[0], "id")
        assert hasattr(accounts[0], "created_at")


class TestDeleteAccount:
    """Tests for delete_account method."""

    def test_delete_account_success(self, account_service, sample_accounts):
        """Test successfully deleting an account."""
        account_id = sample_accounts[0].id
        result = account_service.delete_account(account_id)

        assert result is True

        # Verify account is deleted
        accounts = account_service.list_accounts(queries=(), limit=30, offset=0)
        assert len(accounts) == 4
        assert not any(acc.id == account_id for acc in accounts)

    def test_delete_account_nonexistent(self, account_service, sample_accounts):
        """Test deleting non-existent account returns False."""
        result = account_service.delete_account(99999)

        assert result is False

    def test_delete_account_twice(self, account_service, sample_accounts):
        """Test deleting same account twice."""
        account_id = sample_accounts[0].id

        # First deletion should succeed
        result1 = account_service.delete_account(account_id)
        assert result1 is True

        # Second deletion should fail
        result2 = account_service.delete_account(account_id)
        assert result2 is False

    def test_delete_all_accounts(self, account_service, sample_accounts):
        """Test deleting all accounts."""
        for account in sample_accounts:
            result = account_service.delete_account(account.id)
            assert result is True

        # Verify all deleted
        accounts = account_service.list_accounts(queries=(), limit=30, offset=0)
        assert len(accounts) == 0

    def test_delete_account_does_not_affect_others(
        self, account_service, sample_accounts
    ):
        """Test that deleting one account doesn't affect others."""
        account_to_delete = sample_accounts[2]
        initial_count = len(sample_accounts)

        result = account_service.delete_account(account_to_delete.id)
        assert result is True

        # Verify only one account deleted
        remaining_accounts = account_service.list_accounts(
            queries=(), limit=30, offset=0
        )
        assert len(remaining_accounts) == initial_count - 1
        assert not any(acc.id == account_to_delete.id for acc in remaining_accounts)
        assert all(
            any(
                acc.id == sample.id
                for sample in sample_accounts
                if sample.id != account_to_delete.id
            )
            for acc in remaining_accounts
        )
