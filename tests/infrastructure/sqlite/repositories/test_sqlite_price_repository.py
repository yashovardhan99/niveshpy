"""SQLite price repository unit tests."""

import datetime
from decimal import Decimal
from unittest.mock import patch

import pytest

from niveshpy.core.query.ast import Field, FilterNode, Operator
from niveshpy.exceptions import InvalidInputError
from niveshpy.infrastructure.sqlite.repositories import (
    SqlitePriceRepository,
    SqliteSecurityRepository,
)
from niveshpy.models.price import PriceCreate
from niveshpy.models.security import SecurityCategory, SecurityCreate, SecurityType


@pytest.fixture(scope="function")
def price_repository(session):
    """Provide a fresh SqlitePriceRepository for each test."""
    with patch(
        "niveshpy.infrastructure.sqlite.repositories.sqlite_price_repository.get_session",
        return_value=session,
    ):
        yield SqlitePriceRepository()


@pytest.fixture(scope="function")
def security_repository(session):
    """Provide a fresh SqliteSecurityRepository for each test."""
    with patch(
        "niveshpy.infrastructure.sqlite.repositories.sqlite_security_repository.get_session",
        return_value=session,
    ):
        yield SqliteSecurityRepository()


def test_overwrite_price_persists_row(
    price_repository: SqlitePriceRepository,
    security_repository: SqliteSecurityRepository,
) -> None:
    """Inserting a price persists the row."""
    # First create security to satisfy foreign key constraints
    security_repository.insert_security(
        SecurityCreate(
            key="AAPL",
            name="Apple Inc.",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        )
    )
    price = PriceCreate(
        security_key="AAPL",
        date=datetime.date(2024, 1, 1),
        open=Decimal("150.00"),
        high=Decimal("155.00"),
        low=Decimal("149.00"),
        close=Decimal("154.00"),
    )
    price_repository.overwrite_price(price)
    prices = price_repository.find_all_prices([])
    assert len(prices) == 1
    assert prices[0].security_key == "AAPL"
    assert prices[0].date == datetime.date(2024, 1, 1)
    assert prices[0].open == Decimal("150.00")
    assert prices[0].high == Decimal("155.00")
    assert prices[0].low == Decimal("149.00")
    assert prices[0].close == Decimal("154.00")


def test_overwrite_price_overwrites_existing_price(
    price_repository: SqlitePriceRepository,
    security_repository: SqliteSecurityRepository,
) -> None:
    """Overwriting a price updates the existing row."""
    # First create security to satisfy foreign key constraints
    security_repository.insert_security(
        SecurityCreate(
            key="AAPL",
            name="Apple Inc.",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        )
    )
    price = PriceCreate(
        security_key="AAPL",
        date=datetime.date(2024, 1, 1),
        open=Decimal("150.00"),
        high=Decimal("155.00"),
        low=Decimal("149.00"),
        close=Decimal("154.00"),
    )
    price_repository.overwrite_price(price)
    updated_price = PriceCreate(
        security_key="AAPL",
        date=datetime.date(2024, 1, 1),
        open=Decimal("151.00"),
        high=Decimal("156.00"),
        low=Decimal("150.00"),
        close=Decimal("155.00"),
    )
    price_repository.overwrite_price(updated_price)
    prices = price_repository.find_all_prices([])
    assert len(prices) == 1
    assert prices[0].open == Decimal("151.00")
    assert prices[0].high == Decimal("156.00")
    assert prices[0].low == Decimal("150.00")
    assert prices[0].close == Decimal("155.00")


def test_find_prices_applies_filter_limit_and_offset(
    price_repository: SqlitePriceRepository,
    security_repository: SqliteSecurityRepository,
) -> None:
    """Finding prices applies date filter, limit, and offset correctly."""
    # First create a security to satisfy foreign key constraints
    security_repository.insert_security(
        SecurityCreate(
            key="AAPL",
            name="Apple Inc.",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        )
    )
    prices = [
        PriceCreate(
            security_key="AAPL",
            date=datetime.date(2024, 1, 1),
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("149.00"),
            close=Decimal("154.00"),
        ),
        PriceCreate(
            security_key="AAPL",
            date=datetime.date(2024, 1, 2),
            open=Decimal("151.00"),
            high=Decimal("156.00"),
            low=Decimal("150.00"),
            close=Decimal("155.00"),
        ),
        PriceCreate(
            security_key="AAPL",
            date=datetime.date(2024, 1, 3),
            open=Decimal("152.00"),
            high=Decimal("157.00"),
            low=Decimal("151.00"),
            close=Decimal("156.00"),
        ),
    ]

    price_repository.replace_prices_in_range(
        "AAPL",
        datetime.date(2024, 1, 1),
        datetime.date(2024, 1, 3),
        prices,
        batch_size=2,
    )

    filtered = price_repository.find_all_prices(
        [
            FilterNode(Field.SECURITY, Operator.REGEX_MATCH, "AAPL"),
            FilterNode(
                Field.DATE,
                Operator.BETWEEN,
                (datetime.date(2024, 1, 2), datetime.date(2024, 1, 3)),
            ),
        ]
    )
    assert len(filtered) == 2
    assert filtered[0].date == datetime.date(2024, 1, 2)
    assert filtered[1].date == datetime.date(2024, 1, 3)

    paged = price_repository.find_all_prices([], limit=1, offset=1)
    assert len(paged) == 1
    assert paged[0].date == datetime.date(2024, 1, 2)
    assert paged[0].open == Decimal("151.00")
    assert paged[0].high == Decimal("156.00")
    assert paged[0].low == Decimal("150.00")
    assert paged[0].close == Decimal("155.00")


def test_find_latest_prices(
    price_repository: SqlitePriceRepository,
    security_repository: SqliteSecurityRepository,
) -> None:
    """Finding the latest prices for a security returns the most recent entries."""
    security_repository.insert_security(
        SecurityCreate(
            key="AAPL",
            name="Apple Inc.",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        )
    )
    price_repository.overwrite_price(
        PriceCreate(
            security_key="AAPL",
            date=datetime.date(2024, 1, 1),
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("149.00"),
            close=Decimal("154.00"),
        )
    )
    price_repository.overwrite_price(
        PriceCreate(
            security_key="AAPL",
            date=datetime.date(2024, 1, 2),
            open=Decimal("151.00"),
            high=Decimal("156.00"),
            low=Decimal("150.00"),
            close=Decimal("155.00"),
        )
    )

    latest_prices = price_repository.find_latest_prices([], limit=1)
    assert len(latest_prices) == 1
    assert latest_prices[0].date == datetime.date(2024, 1, 2)
    assert latest_prices[0].open == Decimal("151.00")
    assert latest_prices[0].high == Decimal("156.00")
    assert latest_prices[0].low == Decimal("150.00")
    assert latest_prices[0].close == Decimal("155.00")


def test_get_price_by_key_and_date(
    price_repository: SqlitePriceRepository,
    security_repository: SqliteSecurityRepository,
) -> None:
    """Getting a price by security key and date returns the correct entry."""
    security_repository.insert_security(
        SecurityCreate(
            key="AAPL",
            name="Apple Inc.",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        )
    )
    price_repository.overwrite_price(
        PriceCreate(
            security_key="AAPL",
            date=datetime.date(2024, 1, 1),
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("149.00"),
            close=Decimal("154.00"),
        )
    )

    price = price_repository.get_price_by_key_and_date(
        "AAPL", datetime.date(2024, 1, 1)
    )
    assert price is not None
    assert price.security_key == "AAPL"
    assert price.date == datetime.date(2024, 1, 1)
    assert price.open == Decimal("150.00")
    assert price.high == Decimal("155.00")
    assert price.low == Decimal("149.00")
    assert price.close == Decimal("154.00")


def test_replace_prices_in_range_empty_new_prices(
    price_repository: SqlitePriceRepository,
    security_repository: SqliteSecurityRepository,
) -> None:
    """Replacing prices in a date range with an empty list deletes existing prices without inserting new ones."""
    security_repository.insert_security(
        SecurityCreate(
            key="AAPL",
            name="Apple Inc.",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        )
    )
    price_repository.overwrite_price(
        PriceCreate(
            security_key="AAPL",
            date=datetime.date(2024, 1, 1),
            open=Decimal("150.00"),
            high=Decimal("155.00"),
            low=Decimal("149.00"),
            close=Decimal("154.00"),
        )
    )

    price_repository.replace_prices_in_range(
        "AAPL",
        datetime.date(2024, 1, 1),
        datetime.date(2024, 1, 31),
        [],
        batch_size=2,
    )

    prices = price_repository.find_all_prices([])
    assert len(prices) == 0


def test_replace_prices_in_range_invalid_batch_size(
    price_repository: SqlitePriceRepository,
    security_repository: SqliteSecurityRepository,
) -> None:
    """Replacing prices with an invalid batch size raises an error."""
    security_repository.insert_security(
        SecurityCreate(
            key="AAPL",
            name="Apple Inc.",
            type=SecurityType.STOCK,
            category=SecurityCategory.EQUITY,
        )
    )
    price = PriceCreate(
        security_key="AAPL",
        date=datetime.date(2024, 1, 1),
        open=Decimal("150.00"),
        high=Decimal("155.00"),
        low=Decimal("149.00"),
        close=Decimal("154.00"),
    )

    with pytest.raises(InvalidInputError, match="Batch size"):
        price_repository.replace_prices_in_range(
            "AAPL",
            datetime.date(2024, 1, 1),
            datetime.date(2024, 1, 31),
            [price],
            batch_size=0,
        )
