"""Tests for cattrs converters in niveshpy.core.converter."""

import datetime
from decimal import Decimal

from niveshpy.core.converter import get_csv_converter, get_json_converter
from niveshpy.models.account import AccountPublic
from niveshpy.models.price import PricePublic
from niveshpy.models.report import (
    Allocation,
    Holding,
    PerformanceHolding,
    PortfolioTotals,
    SummaryResult,
)
from niveshpy.models.security import SecurityCategory, SecurityPublic, SecurityType
from niveshpy.models.transaction import TransactionPublic, TransactionType

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_account() -> AccountPublic:
    return AccountPublic(
        id=1,
        name="Savings",
        institution="HDFC",
        created=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
        properties={"source": "cas"},
    )


def _make_security() -> SecurityPublic:
    return SecurityPublic(
        key="MF001",
        name="Equity Fund",
        type=SecurityType.MUTUAL_FUND,
        category=SecurityCategory.EQUITY,
        properties={},
        created=datetime.datetime(2024, 1, 1, tzinfo=datetime.UTC),
    )


def _make_price(*, with_security: bool = True) -> PricePublic:
    return PricePublic(
        security_key="MF001",
        date=datetime.date(2024, 6, 1),
        open=Decimal("100.00"),
        high=Decimal("105.00"),
        low=Decimal("99.00"),
        close=Decimal("102.50"),
        properties={"source": "amfi"},
        created=datetime.datetime(2024, 6, 1, tzinfo=datetime.UTC),
        security=_make_security() if with_security else None,
    )


def _make_transaction(
    *, with_relations: bool = True, with_cost: bool = False
) -> TransactionPublic:
    return TransactionPublic(
        id=1,
        transaction_date=datetime.date(2024, 3, 15),
        type=TransactionType.PURCHASE,
        description="Buy Equity Fund",
        amount=Decimal("1000.00"),
        units=Decimal("10.00"),
        security_key="MF001",
        account_id=1,
        properties={"source": "cas"},
        created=datetime.datetime(2024, 3, 15, tzinfo=datetime.UTC),
        security=_make_security() if with_relations else None,
        account=_make_account() if with_relations else None,
        cost=Decimal("1001.50") if with_cost else None,
    )


def _make_holding() -> Holding:
    return Holding(
        account=_make_account(),
        security=_make_security(),
        date=datetime.date(2024, 6, 1),
        units=Decimal("10"),
        invested=Decimal("1000"),
        amount=Decimal("1100"),
    )


def _make_allocation(
    *,
    security_type: SecurityType | None = SecurityType.MUTUAL_FUND,
    security_category: SecurityCategory | None = SecurityCategory.EQUITY,
) -> Allocation:
    return Allocation(
        date=datetime.date(2024, 6, 1),
        amount=Decimal("1100"),
        allocation=Decimal("0.75"),
        security_type=security_type,
        security_category=security_category,
    )


def _make_perf_holding(
    *,
    invested: Decimal | None = Decimal("1000"),
    xirr: Decimal | None = Decimal("0.12"),
) -> PerformanceHolding:
    return PerformanceHolding(
        account=_make_account(),
        security=_make_security(),
        date=datetime.date(2024, 6, 1),
        current_value=Decimal("1100"),
        invested=invested,
        xirr=xirr,
    )


# ---------------------------------------------------------------------------
# AccountPublic
# ---------------------------------------------------------------------------


class TestAccountPublicJson:
    """Tests for AccountPublic JSON unstructure (default hook)."""

    def test_created_is_isoformat(self):
        """Created datetime is serialised to an ISO string."""
        result = get_json_converter().unstructure(_make_account())
        assert result["created"] == "2024-01-01T00:00:00+00:00"

    def test_source_omitted(self):
        """Source (init=False) is not present in JSON output."""
        result = get_json_converter().unstructure(_make_account())
        assert "source" not in result

    def test_properties_present(self):
        """Properties dict is included in JSON output."""
        result = get_json_converter().unstructure(_make_account())
        assert result["properties"] == {"source": "cas"}

    def test_basic_fields(self):
        """Basic scalar fields are serialised correctly."""
        result = get_json_converter().unstructure(_make_account())
        assert result["id"] == 1
        assert result["name"] == "Savings"
        assert result["institution"] == "HDFC"


class TestAccountPublicCsv:
    """Tests for AccountPublic CSV unstructure."""

    def test_source_present(self):
        """Source field is included in CSV output."""
        result = get_csv_converter().unstructure(_make_account())
        assert result["source"] == "cas"

    def test_properties_omitted(self):
        """Properties dict is omitted from CSV output."""
        result = get_csv_converter().unstructure(_make_account())
        assert "properties" not in result

    def test_created_is_isoformat(self):
        """Created datetime is serialised to an ISO string."""
        result = get_csv_converter().unstructure(_make_account())
        assert result["created"] == "2024-01-01T00:00:00+00:00"

    def test_source_none_when_not_in_properties(self):
        """Source is None when properties has no source key."""
        acc = AccountPublic(
            id=2,
            name="X",
            institution="Y",
            created=datetime.datetime(2024, 1, 1),
            properties={},
        )
        result = get_csv_converter().unstructure(acc)
        assert result["source"] is None


# ---------------------------------------------------------------------------
# SecurityPublic
# ---------------------------------------------------------------------------


class TestSecurityPublicJson:
    """Tests for SecurityPublic JSON unstructure (default hook)."""

    def test_enums_as_strings(self):
        """Type and category are serialised as their string values."""
        result = get_json_converter().unstructure(_make_security())
        assert result["type"] == "mutual_fund"
        assert result["category"] == "equity"

    def test_source_omitted(self):
        """Source (init=False) is not present in JSON output."""
        result = get_json_converter().unstructure(_make_security())
        assert "source" not in result

    def test_properties_present(self):
        """Properties dict is included."""
        result = get_json_converter().unstructure(_make_security())
        assert result["properties"] == {}

    def test_created_is_isoformat(self):
        """Created datetime is serialised to an ISO string."""
        result = get_json_converter().unstructure(_make_security())
        assert result["created"] == "2024-01-01T00:00:00+00:00"


class TestSecurityPublicCsv:
    """Tests for SecurityPublic CSV unstructure."""

    def test_source_present(self):
        """Source field is included in CSV output."""
        sec = SecurityPublic(
            key="MF001",
            name="Equity Fund",
            type=SecurityType.MUTUAL_FUND,
            category=SecurityCategory.EQUITY,
            properties={"source": "amfi"},
            created=datetime.datetime(2024, 1, 1),
        )
        result = get_csv_converter().unstructure(sec)
        assert result["source"] == "amfi"

    def test_properties_omitted(self):
        """Properties dict is omitted from CSV output."""
        result = get_csv_converter().unstructure(_make_security())
        assert "properties" not in result

    def test_enums_as_strings(self):
        """Type and category are serialised as their string values."""
        result = get_csv_converter().unstructure(_make_security())
        assert result["type"] == "mutual_fund"
        assert result["category"] == "equity"


# ---------------------------------------------------------------------------
# PricePublic
# ---------------------------------------------------------------------------


class TestPricePublicJson:
    """Tests for PricePublic JSON unstructure."""

    def test_security_key_omitted(self):
        """security_key is omitted from JSON output."""
        result = get_json_converter().unstructure(_make_price())
        assert "security_key" not in result

    def test_nested_security_present(self):
        """Nested security object is included."""
        result = get_json_converter().unstructure(_make_price(with_security=True))
        assert isinstance(result["security"], dict)
        assert result["security"]["key"] == "MF001"

    def test_nested_security_none(self):
        """Security key is None when security not set."""
        result = get_json_converter().unstructure(_make_price(with_security=False))
        assert result["security"] is None

    def test_decimals_as_strings(self):
        """Decimal fields are serialised as strings."""
        result = get_json_converter().unstructure(_make_price())
        assert result["close"] == "102.50"

    def test_date_is_isoformat(self):
        """Date field is serialised to ISO string."""
        result = get_json_converter().unstructure(_make_price())
        assert result["date"] == "2024-06-01"

    def test_properties_present(self):
        """Properties dict is included in JSON output."""
        result = get_json_converter().unstructure(_make_price())
        assert result["properties"] == {"source": "amfi"}


class TestPricePublicCsv:
    """Tests for PricePublic CSV unstructure."""

    def test_security_object_omitted(self):
        """Nested security object is omitted."""
        result = get_csv_converter().unstructure(_make_price())
        assert "security" not in result or not isinstance(result.get("security"), dict)

    def test_security_key_renamed_to_security(self):
        """security_key field appears under the key 'security'."""
        result = get_csv_converter().unstructure(_make_price())
        assert result["security"] == "MF001"

    def test_properties_omitted(self):
        """Properties dict is omitted from CSV output."""
        result = get_csv_converter().unstructure(_make_price())
        assert "properties" not in result

    def test_source_present(self):
        """Source field is included in CSV output."""
        result = get_csv_converter().unstructure(_make_price())
        assert result["source"] == "amfi"


# ---------------------------------------------------------------------------
# TransactionPublic
# ---------------------------------------------------------------------------


class TestTransactionPublicJson:
    """Tests for TransactionPublic JSON unstructure."""

    def test_security_key_and_account_id_omitted(self):
        """security_key and account_id are omitted from JSON output."""
        result = get_json_converter().unstructure(_make_transaction())
        assert "security_key" not in result
        assert "account_id" not in result

    def test_nested_relations_present(self):
        """Nested security and account objects are present."""
        result = get_json_converter().unstructure(
            _make_transaction(with_relations=True)
        )
        assert isinstance(result["security"], dict)
        assert result["security"]["key"] == "MF001"
        assert isinstance(result["account"], dict)
        assert result["account"]["id"] == 1

    def test_nested_relations_none(self):
        """Security and account keys are None when not set."""
        result = get_json_converter().unstructure(
            _make_transaction(with_relations=False)
        )
        assert result["security"] is None
        assert result["account"] is None

    def test_cost_omitted_when_none(self):
        """Cost field is omitted from output when None."""
        result = get_json_converter().unstructure(_make_transaction(with_cost=False))
        assert "cost" not in result

    def test_cost_present_when_set(self):
        """Cost field is present in output when set."""
        result = get_json_converter().unstructure(_make_transaction(with_cost=True))
        assert result["cost"] == "1001.50"

    def test_decimals_as_strings(self):
        """Decimal fields are serialised as strings."""
        result = get_json_converter().unstructure(_make_transaction())
        assert result["amount"] == "1000.00"

    def test_type_as_string(self):
        """TransactionType enum is serialised as its string value."""
        result = get_json_converter().unstructure(_make_transaction())
        assert result["type"] == "purchase"

    def test_source_omitted(self):
        """Source (init=False) is omitted from JSON output."""
        result = get_json_converter().unstructure(_make_transaction())
        assert "source" not in result


class TestTransactionPublicCsv:
    """Tests for TransactionPublic CSV unstructure."""

    def test_security_key_renamed_to_security(self):
        """security_key appears under key 'security'."""
        result = get_csv_converter().unstructure(_make_transaction())
        assert result["security"] == "MF001"

    def test_account_id_renamed_to_account(self):
        """account_id appears under key 'account'."""
        result = get_csv_converter().unstructure(_make_transaction())
        assert result["account"] == 1

    def test_nested_objects_omitted(self):
        """Nested security and account objects are omitted."""
        result = get_csv_converter().unstructure(_make_transaction(with_relations=True))
        assert not isinstance(result.get("security"), dict)
        assert not isinstance(result.get("account"), dict)

    def test_properties_omitted(self):
        """Properties dict is omitted from CSV output."""
        result = get_csv_converter().unstructure(_make_transaction())
        assert "properties" not in result

    def test_source_present(self):
        """Source field is included in CSV output."""
        result = get_csv_converter().unstructure(_make_transaction())
        assert result["source"] == "cas"

    def test_cost_omitted_when_none(self):
        """Cost field is omitted when None."""
        result = get_csv_converter().unstructure(_make_transaction(with_cost=False))
        assert "cost" not in result

    def test_cost_present_when_set(self):
        """Cost field is present and is a Decimal (not string) in CSV."""
        result = get_csv_converter().unstructure(_make_transaction(with_cost=True))
        assert result["cost"] == Decimal("1001.50")


# ---------------------------------------------------------------------------
# Holding
# ---------------------------------------------------------------------------


class TestHoldingJson:
    """Tests for Holding JSON unstructure."""

    def test_amount_renamed_to_current(self):
        """Amount field appears under key 'current' in JSON output."""
        result = get_json_converter().unstructure(_make_holding())
        assert "current" in result
        assert "amount" not in result
        assert result["current"] == "1100"

    def test_nested_account_present(self):
        """Nested account is fully unstructured."""
        result = get_json_converter().unstructure(_make_holding())
        assert isinstance(result["account"], dict)
        assert result["account"]["id"] == 1

    def test_nested_security_present(self):
        """Nested security is fully unstructured."""
        result = get_json_converter().unstructure(_make_holding())
        assert isinstance(result["security"], dict)
        assert result["security"]["key"] == "MF001"

    def test_convenience_fields_omitted(self):
        """account_id and security_key (init=False) are omitted."""
        result = get_json_converter().unstructure(_make_holding())
        assert "account_id" not in result
        assert "security_key" not in result

    def test_date_is_isoformat(self):
        """Date field is serialised to ISO string."""
        result = get_json_converter().unstructure(_make_holding())
        assert result["date"] == "2024-06-01"

    def test_decimals_as_strings(self):
        """Decimal fields are serialised as strings."""
        result = get_json_converter().unstructure(_make_holding())
        assert result["units"] == "10"
        assert result["invested"] == "1000"


class TestHoldingCsv:
    """Tests for Holding CSV unstructure."""

    def test_account_is_id(self):
        """Account field contains the account ID (int)."""
        result = get_csv_converter().unstructure(_make_holding())
        assert result["account"] == 1

    def test_security_is_key(self):
        """Security field contains the security key (str)."""
        result = get_csv_converter().unstructure(_make_holding())
        assert result["security"] == "MF001"

    def test_amount_renamed_to_current(self):
        """Amount field appears under key 'current'."""
        result = get_csv_converter().unstructure(_make_holding())
        assert "current" in result
        assert "amount" not in result
        assert result["current"] == Decimal("1100")

    def test_convenience_fields_omitted(self):
        """account_id and security_key are omitted."""
        result = get_csv_converter().unstructure(_make_holding())
        assert "account_id" not in result
        assert "security_key" not in result

    def test_decimals_remain_as_decimal(self):
        """Decimal fields are not converted to strings in CSV."""
        result = get_csv_converter().unstructure(_make_holding())
        assert isinstance(result["units"], Decimal)
        assert isinstance(result["invested"], Decimal)


# ---------------------------------------------------------------------------
# Allocation
# ---------------------------------------------------------------------------


class TestAllocationJson:
    """Tests for Allocation JSON unstructure."""

    def test_both_type_and_category_present(self):
        """Both security_type and security_category are present when set."""
        result = get_json_converter().unstructure(_make_allocation())
        assert result["security_type"] == "mutual_fund"
        assert result["security_category"] == "equity"

    def test_type_only(self):
        """Only security_type is present when category is None."""
        result = get_json_converter().unstructure(
            _make_allocation(
                security_type=SecurityType.MUTUAL_FUND, security_category=None
            )
        )
        assert result["security_type"] == "mutual_fund"
        assert "security_category" not in result

    def test_category_only(self):
        """Only security_category is present when type is None."""
        result = get_json_converter().unstructure(
            _make_allocation(
                security_type=None, security_category=SecurityCategory.DEBT
            )
        )
        assert result["security_category"] == "debt"
        assert "security_type" not in result

    def test_decimals_as_strings(self):
        """Decimal fields are serialised as strings."""
        result = get_json_converter().unstructure(_make_allocation())
        assert result["amount"] == "1100"
        assert result["allocation"] == "0.75"

    def test_date_is_isoformat(self):
        """Date field is serialised to ISO string."""
        result = get_json_converter().unstructure(_make_allocation())
        assert result["date"] == "2024-06-01"


class TestAllocationCsv:
    """Tests for Allocation CSV unstructure."""

    def test_both_present(self):
        """Both security_type and security_category present when set."""
        result = get_csv_converter().unstructure(_make_allocation())
        assert result["security_type"] == "mutual_fund"
        assert result["security_category"] == "equity"

    def test_type_only(self):
        """Only security_type is present when category is None."""
        result = get_csv_converter().unstructure(
            _make_allocation(security_type=SecurityType.ETF, security_category=None)
        )
        assert result["security_type"] == "etf"
        assert "security_category" not in result

    def test_category_only(self):
        """Only security_category is present when type is None."""
        result = get_csv_converter().unstructure(
            _make_allocation(
                security_type=None, security_category=SecurityCategory.DEBT
            )
        )
        assert result["security_category"] == "debt"
        assert "security_type" not in result

    def test_decimals_remain_as_decimal(self):
        """Decimal fields are not converted to strings in CSV."""
        result = get_csv_converter().unstructure(_make_allocation())
        assert isinstance(result["amount"], Decimal)
        assert isinstance(result["allocation"], Decimal)


# ---------------------------------------------------------------------------
# PerformanceHolding
# ---------------------------------------------------------------------------


class TestPerformanceHoldingJson:
    """Tests for PerformanceHolding JSON unstructure."""

    def test_nested_account_and_security_present(self):
        """Nested account and security objects are included."""
        result = get_json_converter().unstructure(_make_perf_holding())
        assert isinstance(result["account"], dict)
        assert isinstance(result["security"], dict)

    def test_convenience_fields_omitted(self):
        """account_id and security_key (init=False) are omitted."""
        result = get_json_converter().unstructure(_make_perf_holding())
        assert "account_id" not in result
        assert "security_key" not in result

    def test_gains_and_gains_pct_present(self):
        """Gains and gains_pct (init=False) are included."""
        result = get_json_converter().unstructure(_make_perf_holding())
        assert result["gains"] == "100"
        assert result["gains_pct"] == "0.1000"

    def test_xirr_as_string(self):
        """Xirr Decimal is serialised as string."""
        result = get_json_converter().unstructure(_make_perf_holding())
        assert result["xirr"] == "0.12"

    def test_xirr_none(self):
        """xirr=None serialises to None."""
        result = get_json_converter().unstructure(_make_perf_holding(xirr=None))
        assert result["xirr"] is None

    def test_invested_none_yields_none_gains(self):
        """invested=None → gains and gains_pct are None."""
        result = get_json_converter().unstructure(_make_perf_holding(invested=None))
        assert result["invested"] is None
        assert result["gains"] is None
        assert result["gains_pct"] is None

    def test_date_is_isoformat(self):
        """Date field is serialised to ISO string."""
        result = get_json_converter().unstructure(_make_perf_holding())
        assert result["date"] == "2024-06-01"


class TestPerformanceHoldingCsv:
    """Tests for PerformanceHolding CSV unstructure."""

    def test_account_is_id(self):
        """Account field contains the account ID (int)."""
        result = get_csv_converter().unstructure(_make_perf_holding())
        assert result["account"] == 1

    def test_security_is_key(self):
        """Security field contains the security key (str)."""
        result = get_csv_converter().unstructure(_make_perf_holding())
        assert result["security"] == "MF001"

    def test_nested_objects_omitted(self):
        """Nested account and security objects are omitted."""
        result = get_csv_converter().unstructure(_make_perf_holding())
        assert not isinstance(result.get("account"), dict)
        assert not isinstance(result.get("security"), dict)

    def test_gains_and_gains_pct_present(self):
        """Gains and gains_pct (init=False) are included as Decimals."""
        result = get_csv_converter().unstructure(_make_perf_holding())
        assert isinstance(result["gains"], Decimal)
        assert isinstance(result["gains_pct"], Decimal)

    def test_invested_none_yields_none_gains(self):
        """invested=None → gains and gains_pct are None."""
        result = get_csv_converter().unstructure(_make_perf_holding(invested=None))
        assert result["gains"] is None
        assert result["gains_pct"] is None

    def test_decimals_remain_as_decimal(self):
        """Decimal fields are not converted to strings in CSV."""
        result = get_csv_converter().unstructure(_make_perf_holding())
        assert isinstance(result["current_value"], Decimal)


# ---------------------------------------------------------------------------
# SummaryResult (JSON only)
# ---------------------------------------------------------------------------


class TestSummaryResultJson:
    """Tests for SummaryResult JSON unstructure."""

    def _make_summary(
        self, *, as_of: datetime.date | None = datetime.date(2024, 6, 1)
    ) -> SummaryResult:
        return SummaryResult(
            as_of=as_of,
            metrics=PortfolioTotals(
                total_current_value=Decimal("1100"),
                total_invested=Decimal("1000"),
                total_gains=Decimal("100"),
                gains_percentage=Decimal("0.10"),
                xirr=Decimal("0.12"),
                last_updated=datetime.date(2024, 6, 1),
            ),
            top_holdings=[_make_perf_holding()],
            allocation=[_make_allocation()],
        )

    def test_as_of_renamed_to_date(self):
        """as_of field appears under key 'date'."""
        result = get_json_converter().unstructure(self._make_summary())
        assert "date" in result
        assert "as_of" not in result
        assert result["date"] == "2024-06-01"

    def test_as_of_none(self):
        """as_of=None serialises to 'date': None."""
        result = get_json_converter().unstructure(self._make_summary(as_of=None))
        assert result["date"] is None

    def test_metrics_is_dict(self):
        """Metrics is a dict with all PortfolioTotals fields."""
        result = get_json_converter().unstructure(self._make_summary())
        assert isinstance(result["metrics"], dict)
        assert result["metrics"]["total_current_value"] == "1100"
        assert result["metrics"]["xirr"] == "0.12"
        assert result["metrics"]["last_updated"] == "2024-06-01"

    def test_top_holdings_is_list_of_dicts(self):
        """top_holdings is a list of unstructured PerformanceHolding dicts."""
        result = get_json_converter().unstructure(self._make_summary())
        assert isinstance(result["top_holdings"], list)
        assert len(result["top_holdings"]) == 1
        assert isinstance(result["top_holdings"][0]["account"], dict)

    def test_allocation_is_list_of_dicts(self):
        """Allocation is a list of unstructured Allocation dicts."""
        result = get_json_converter().unstructure(self._make_summary())
        assert isinstance(result["allocation"], list)
        assert len(result["allocation"]) == 1
        assert result["allocation"][0]["security_type"] == "mutual_fund"
