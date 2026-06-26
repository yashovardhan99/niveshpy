"""Transaction validation service for NiveshPy."""

from collections.abc import Sequence
from typing import Protocol

from attrs import evolve, frozen

from niveshpy.core.logging import logger
from niveshpy.models.transaction import TransactionCreate, TransactionType


class TransactionValidator(Protocol):
    """Protocol for transaction validators.

    This protocol defines the interface that any transaction validator must implement.
    Validators are responsible for validating transactions based on specific rules and criteria.
    """

    def validate(
        self,
        transactions: Sequence[TransactionCreate],
    ) -> Sequence[TransactionCreate]:
        """Validate a sequence of transactions.

        Args:
            transactions (Sequence[TransactionCreate]): A sequence of transactions to validate.

        Returns:
            Sequence[TransactionCreate]: A sequence of validated transactions.
        """
        ...


@frozen
class TransactionValidationService:
    """Service for validating transactions.

    This service provides methods to validate transactions based on their type and other attributes.
    It ensures that transactions adhere to the expected rules and constraints defined for each transaction type.
    """

    validators: Sequence[TransactionValidator]

    def validate(
        self, transactions: Sequence[TransactionCreate]
    ) -> Sequence[TransactionCreate]:
        """Validate a sequence of transactions.

        The service calls a pipeline of validators to validate the transactions.
        Each validator checks for specific rules and constraints. This service groups
        the transactions by (account, security) before passing them to the validators.

        Args:
            transactions (Sequence[TransactionCreate]): A sequence of transactions to validate.

        Returns:
            Sequence[TransactionCreate]: A sequence of validated transactions.

        Raises:
            ValueError: If any transaction fails validation.
        """
        # Group transactions by (account, security)
        grouped_transactions = {}
        for txn in transactions:
            key = (txn.account_id, txn.security_key)
            if key not in grouped_transactions:
                grouped_transactions[key] = []
            grouped_transactions[key].append(txn)

        # Validate each group of transactions using the validators
        validated_transactions = []
        for group in grouped_transactions.values():
            # Apply each validator in the pipeline to the group of transactions
            for validator in self.validators:
                group = validator.validate(group)

            # Add the validated group to the final list
            validated_transactions.extend(group)

        return validated_transactions


@frozen
class TransactionReversalValidator:
    """Validator for transaction reversals.

    This validator maps a reversal transaction to its corresponding original transaction and
    checks for consistency. It ensures that the reversal transaction correctly negates the
    effects of the original transaction. Further, it marks both the original and reversal
    transactions as ignored to prevent them from affecting account balances or reports.

    Attributes:
        strict (bool): If True, the validator will raise an error for unmatched reversals.
    """

    strict: bool = False

    def validate(
        self,
        transactions: Sequence[TransactionCreate],
    ) -> Sequence[TransactionCreate]:
        """Validate reversal transactions.

        Args:
            transactions (Sequence[TransactionCreate]): A sequence of transactions to validate.

        Returns:
            Sequence[TransactionCreate]: A sequence of validated transactions.

        Raises:
            ValueError: If any reversal transaction does not have a corresponding original transaction.
        """
        # Sort transactions in reverse chronological order to ensure reversals are found before
        # their corresponding original transactions
        sorted_transactions = sorted(
            transactions,
            key=lambda txn: (
                txn.transaction_date,
                txn.type == TransactionType.REVERSAL,
            ),
            reverse=True,
        )

        # Create a hash map to track reversal transactions
        reversal_map = {}

        validated_transactions = []

        for txn in sorted_transactions:
            if txn.type == TransactionType.REVERSAL:
                key = (txn.amount, txn.units)
                if key not in reversal_map:
                    reversal_map[key] = []
                # If it's a reversal, add it to the map with its corresponding original transaction ID
                reversal_map[key].append(txn)
            else:
                # If it's an original transaction, check if there's a corresponding reversal
                if (-txn.amount, -txn.units) in reversal_map:
                    for candidate_reversal in reversal_map[(-txn.amount, -txn.units)]:
                        # Check if the reversal transaction is within a reasonable time frame (e.g., 2 days)
                        if (
                            candidate_reversal.transaction_date - txn.transaction_date
                        ).days <= 2:
                            # Remove the reversal from the map as it's been matched
                            reversal_map[(-txn.amount, -txn.units)].remove(
                                candidate_reversal
                            )

                            original, reversal = (
                                evolve(txn, is_ignored=True),
                                evolve(candidate_reversal, is_ignored=True),
                            )
                            logger.info(
                                "Marking original transaction %s and reversal transaction %s as ignored.",
                                original,
                                reversal,
                            )
                            validated_transactions.extend([original, reversal])
                            break
                    else:
                        # No matching reversal found for this original transaction
                        validated_transactions.append(txn)
                else:
                    # No matching reversal found for this original transaction
                    validated_transactions.append(txn)

        # Check if there are any unmatched reversal transactions left in the map
        exceptions = []
        for unmatched_reversals in reversal_map.values():
            for unmatched_reversal in unmatched_reversals:
                if self.strict:
                    exceptions.append(
                        ValueError(
                            f"Unmatched reversal transaction found: {unmatched_reversal}. No corresponding original transaction."
                        )
                    )
                else:
                    logger.warning(
                        "Unmatched reversal transaction found: %s. No corresponding original transaction.",
                        unmatched_reversal,
                    )
                    validated_transactions.append(unmatched_reversal)

        if exceptions:
            raise ExceptionGroup(
                "One or more unmatched reversal transactions were found. See details below.",
                exceptions,
            )

        return validated_transactions


def get_transaction_validation_service(
    strict: bool = False,
) -> TransactionValidationService:
    """Factory function to create a TransactionValidationService instance.

    Args:
        strict (bool): If True, the validator will raise an error for unmatched reversals.

    Returns:
        TransactionValidationService: An instance of the transaction validation service
        with the necessary validators configured.
    """
    validators = [
        TransactionReversalValidator(strict=strict),
        # Add other validators here as needed
    ]
    return TransactionValidationService(validators=validators)
