"""Service for parsing financial documents."""

import polars as pl
from niveshpy.models.parser import Parser
from niveshpy.cli.app import Application


class ParsingService:
    """Service for parsing financial documents."""

    def __init__(
        self,
        parser: Parser,
        application: Application,
    ):
        """Initialize the ParsingService."""
        self._parser = parser
        self._account_service = application.account_service
        self._security_service = application.security_service
        self._transaction_service = application.transaction_service

    def process(self):
        """Process the parsed data and store it in the database."""
        accounts = self._parser.get_accounts()
        self._account_service.add_accounts(accounts)

        securities = self._parser.get_securities()
        print(securities)
        self._security_service.add_securities(securities)

        transactions = self._parser.get_transactions()
        if isinstance(transactions, pl.DataFrame):
            df = transactions
            if "account_key" not in df.columns:
                accounts_df = self._account_service.get_accounts()
                df = df.join(
                    accounts_df.select(
                        pl.col("id").alias("account_key"),
                        pl.col("name").alias("account_name"),
                        pl.col("institution").alias("account_institution"),
                    ),
                    on=["account_name", "account_institution"],
                    how="left",
                ).drop(["account_name", "account_institution"])
        else:
            df = pl.from_dicts(transactions)

        self._transaction_service.add_transactions(df)
