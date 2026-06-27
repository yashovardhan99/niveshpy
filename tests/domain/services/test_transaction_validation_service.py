"""Test cases for the TransactionValidationService."""

import datetime
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from niveshpy.domain.services.transaction_validation import (
    TransactionReversalValidator,
    TransactionValidationService,
    get_transaction_validation_service,
)
from niveshpy.models.transaction import TransactionCreate, TransactionType


class TestTransactionReversalValidator:
    """Test cases for the TransactionReversalValidator."""

    @pytest.fixture
    def base_date(self):
        """Base date for test transactions."""
        return datetime.date(2024, 6, 1)

    def test_matched_pair_same_day(self, base_date):
        """REVERSAL on day 3, original PURCHASE on day 3: both returned with is_ignored=True."""
        original = TransactionCreate(
            transaction_date=base_date,
            type=TransactionType.PURCHASE,
            description="Original purchase",
            amount=Decimal("100.00"),
            units=Decimal("10.00"),
            security_key="SEC001",
            account_id=1,
        )
        reversal = TransactionCreate(
            transaction_date=base_date,
            type=TransactionType.REVERSAL,
            description="Reversal",
            amount=Decimal("-100.00"),
            units=Decimal("-10.00"),
            security_key="SEC001",
            account_id=1,
        )

        validator = TransactionReversalValidator()
        result = validator.validate([original, reversal])

        assert len(result) == 2
        assert all(txn.is_ignored for txn in result)

    def test_within_date_window(self, base_date):
        """REVERSAL on day 5, original on day 3 (diff=2): matches."""
        original = TransactionCreate(
            transaction_date=base_date,
            type=TransactionType.PURCHASE,
            description="Original purchase",
            amount=Decimal("100.00"),
            units=Decimal("10.00"),
            security_key="SEC001",
            account_id=1,
        )
        reversal = TransactionCreate(
            transaction_date=base_date + datetime.timedelta(days=2),
            type=TransactionType.REVERSAL,
            description="Reversal",
            amount=Decimal("-100.00"),
            units=Decimal("-10.00"),
            security_key="SEC001",
            account_id=1,
        )

        validator = TransactionReversalValidator()
        result = validator.validate([original, reversal])

        assert len(result) == 2
        assert all(txn.is_ignored for txn in result)

    def test_outside_date_window(self, base_date):
        """diff=3 days: no match, both pass through unchanged."""
        original = TransactionCreate(
            transaction_date=base_date,
            type=TransactionType.PURCHASE,
            description="Original purchase",
            amount=Decimal("100.00"),
            units=Decimal("10.00"),
            security_key="SEC001",
            account_id=1,
        )
        reversal = TransactionCreate(
            transaction_date=base_date + datetime.timedelta(days=3),
            type=TransactionType.REVERSAL,
            description="Reversal",
            amount=Decimal("-100.00"),
            units=Decimal("-10.00"),
            security_key="SEC001",
            account_id=1,
        )

        validator = TransactionReversalValidator()
        result = validator.validate([original, reversal])

        assert len(result) == 2
        # Neither should be ignored since they're outside the window
        assert not result[0].is_ignored
        assert not result[1].is_ignored

    def test_same_date_ordering(self, base_date):
        """REVERSAL and original both on day 3, original appears first in input list: still matches."""
        original = TransactionCreate(
            transaction_date=base_date,
            type=TransactionType.PURCHASE,
            description="Original purchase",
            amount=Decimal("100.00"),
            units=Decimal("10.00"),
            security_key="SEC001",
            account_id=1,
        )
        reversal = TransactionCreate(
            transaction_date=base_date,
            type=TransactionType.REVERSAL,
            description="Reversal",
            amount=Decimal("-100.00"),
            units=Decimal("-10.00"),
            security_key="SEC001",
            account_id=1,
        )

        validator = TransactionReversalValidator()
        # Input order doesn't matter; should still match
        result = validator.validate([original, reversal])

        assert len(result) == 2
        assert all(txn.is_ignored for txn in result)

    def test_unmatched_reversal_non_strict(self, base_date):
        """REVERSAL with no corresponding original: returned unchanged, is_ignored=False."""
        reversal = TransactionCreate(
            transaction_date=base_date,
            type=TransactionType.REVERSAL,
            description="Unmatched reversal",
            amount=Decimal("-100.00"),
            units=Decimal("-10.00"),
            security_key="SEC001",
            account_id=1,
        )

        validator = TransactionReversalValidator(strict=False)
        result = validator.validate([reversal])

        assert len(result) == 1
        assert not result[0].is_ignored
        assert result[0].type == TransactionType.REVERSAL

    def test_unmatched_reversal_strict(self, base_date):
        """Unmatched reversal in strict mode: raises ExceptionGroup containing ValueError."""
        reversal = TransactionCreate(
            transaction_date=base_date,
            type=TransactionType.REVERSAL,
            description="Unmatched reversal",
            amount=Decimal("-100.00"),
            units=Decimal("-10.00"),
            security_key="SEC001",
            account_id=1,
        )

        validator = TransactionReversalValidator(strict=True)
        with pytest.raises(ExceptionGroup) as exc_info:
            validator.validate([reversal])

        assert "unmatched reversal" in str(exc_info.value).lower()

    def test_original_without_reversal(self, base_date):
        """Original without reversal: passes through unchanged, is_ignored=False."""
        original = TransactionCreate(
            transaction_date=base_date,
            type=TransactionType.PURCHASE,
            description="Original purchase",
            amount=Decimal("100.00"),
            units=Decimal("10.00"),
            security_key="SEC001",
            account_id=1,
        )

        validator = TransactionReversalValidator()
        result = validator.validate([original])

        assert len(result) == 1
        assert not result[0].is_ignored

    def test_multiple_pairs_same_amount(self, base_date):
        """Two originals, two reversals with same amount/units: each matched exactly once."""
        original1 = TransactionCreate(
            transaction_date=base_date,
            type=TransactionType.PURCHASE,
            description="Original 1",
            amount=Decimal("100.00"),
            units=Decimal("10.00"),
            security_key="SEC001",
            account_id=1,
        )
        original2 = TransactionCreate(
            transaction_date=base_date,
            type=TransactionType.PURCHASE,
            description="Original 2",
            amount=Decimal("100.00"),
            units=Decimal("10.00"),
            security_key="SEC001",
            account_id=1,
        )
        reversal1 = TransactionCreate(
            transaction_date=base_date + datetime.timedelta(days=1),
            type=TransactionType.REVERSAL,
            description="Reversal 1",
            amount=Decimal("-100.00"),
            units=Decimal("-10.00"),
            security_key="SEC001",
            account_id=1,
        )
        reversal2 = TransactionCreate(
            transaction_date=base_date + datetime.timedelta(days=1),
            type=TransactionType.REVERSAL,
            description="Reversal 2",
            amount=Decimal("-100.00"),
            units=Decimal("-10.00"),
            security_key="SEC001",
            account_id=1,
        )

        validator = TransactionReversalValidator()
        result = validator.validate([original1, original2, reversal1, reversal2])

        assert len(result) == 4
        # All should be ignored since each pair matches
        assert sum(1 for txn in result if txn.is_ignored) == 4


class TestTransactionValidationService:
    """Test cases for TransactionValidationService."""

    @pytest.fixture
    def base_date(self):
        """Base date for test transactions."""
        return datetime.date(2024, 6, 1)

    def test_groups_by_account_and_security(self, base_date):
        """REVERSAL in account A does NOT mark original in account B as ignored."""
        original_account_a = TransactionCreate(
            transaction_date=base_date,
            type=TransactionType.PURCHASE,
            description="Original in A",
            amount=Decimal("100.00"),
            units=Decimal("10.00"),
            security_key="SEC001",
            account_id=1,
        )
        reversal_account_b = TransactionCreate(
            transaction_date=base_date,
            type=TransactionType.REVERSAL,
            description="Reversal in B",
            amount=Decimal("-100.00"),
            units=Decimal("-10.00"),
            security_key="SEC001",
            account_id=2,
        )

        validator = TransactionReversalValidator()
        service = TransactionValidationService(validators=[validator])
        result = service.validate([original_account_a, reversal_account_b])

        assert len(result) == 2
        # Original in A should not be ignored (no matching reversal in A)
        assert result[0].account_id == 1
        assert not result[0].is_ignored
        # Reversal in B should not be ignored (no matching original in B)
        assert result[1].account_id == 2
        assert not result[1].is_ignored

    def test_empty_input(self):
        """Empty input returns empty output."""
        validator = TransactionReversalValidator()
        service = TransactionValidationService(validators=[validator])
        result = service.validate([])

        assert result == []

    def test_validator_pipeline_order(self, base_date):
        """Validators are called per group; verify pipeline execution order."""
        original = TransactionCreate(
            transaction_date=base_date,
            type=TransactionType.PURCHASE,
            description="Original",
            amount=Decimal("100.00"),
            units=Decimal("10.00"),
            security_key="SEC001",
            account_id=1,
        )

        # Create a mock validator that records calls
        mock_validator = MagicMock()
        mock_validator.validate.side_effect = lambda txns: txns

        service = TransactionValidationService(validators=[mock_validator])
        service.validate([original])

        # Verify the validator was called once
        assert mock_validator.validate.call_count == 1
        # Verify it received the transaction
        called_txns = mock_validator.validate.call_args[0][0]
        assert len(called_txns) == 1
        assert called_txns[0].description == "Original"


class TestGetTransactionValidationService:
    """Test cases for get_transaction_validation_service factory function."""

    def test_returns_transaction_validation_service(self):
        """Factory returns a TransactionValidationService instance."""
        service = get_transaction_validation_service()

        assert isinstance(service, TransactionValidationService)

    def test_has_reversal_validator(self):
        """Returned service has one validator of type TransactionReversalValidator."""
        service = get_transaction_validation_service()

        assert len(service.validators) == 1
        assert isinstance(service.validators[0], TransactionReversalValidator)

    def test_strict_propagates_to_validator(self):
        """strict=True propagates to the validator's .strict attribute."""
        service_non_strict = get_transaction_validation_service(strict=False)
        service_strict = get_transaction_validation_service(strict=True)

        validator_non_strict = service_non_strict.validators[0]
        assert isinstance(validator_non_strict, TransactionReversalValidator)
        assert validator_non_strict.strict is False

        validator_strict = service_strict.validators[0]
        assert isinstance(validator_strict, TransactionReversalValidator)
        assert validator_strict.strict is True
