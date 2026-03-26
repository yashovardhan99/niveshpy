"""Tests for parser registration and discovery."""

from unittest.mock import MagicMock, patch

import pytest

from niveshpy.core.parsers import (
    discover_installed_parsers,
    get_parser,
    is_empty,
    list_parsers,
    list_parsers_starting_with,
    register_parser,
)
from niveshpy.models.parser import ParserInfo


class MockParserFactory:
    """Mock parser factory satisfying the ParserFactory protocol."""

    @classmethod
    def get_parser_info(cls):
        """Get mock parser info."""
        return ParserInfo(
            name="Mock", description="Mock parser", file_extensions=[".mock"]
        )

    @classmethod
    def create_parser(cls, file_path, password=None):
        """Create a mock parser."""
        return MagicMock()


class AnotherMockParserFactory:
    """Second mock factory for multi-registration tests."""

    @classmethod
    def get_parser_info(cls):
        """Get another mock parser info."""
        return ParserInfo(
            name="Another", description="Another mock parser", file_extensions=[".csv"]
        )

    @classmethod
    def create_parser(cls, file_path, password=None):
        """Create another mock parser."""
        return MagicMock()


@pytest.fixture(autouse=True)
def clean_registry():
    """Clear parser registry and caches before and after each test."""
    from niveshpy.core import parsers

    parsers._REGISTERED_PARSERS.clear()
    parsers.list_parsers.cache_clear()
    parsers.list_parsers_starting_with.cache_clear()
    yield
    parsers._REGISTERED_PARSERS.clear()
    parsers.list_parsers.cache_clear()
    parsers.list_parsers_starting_with.cache_clear()


class TestRegisterParser:
    """Test register_parser function."""

    def test_register_new_parser(self):
        """Test registering a new parser adds it to the registry."""
        register_parser("mock_parser", MockParserFactory)

        assert get_parser("mock_parser") is MockParserFactory

    def test_register_overwrites_existing(self):
        """Test registering with the same key overwrites the previous factory."""
        register_parser("mock_parser", MockParserFactory)
        register_parser("mock_parser", AnotherMockParserFactory)

        assert get_parser("mock_parser") is AnotherMockParserFactory


class TestGetParser:
    """Test get_parser function."""

    def test_get_registered_parser(self):
        """Test retrieving a registered parser returns the correct factory."""
        register_parser("mock_parser", MockParserFactory)

        result = get_parser("mock_parser")
        assert result is MockParserFactory

    def test_get_unregistered_returns_none(self):
        """Test retrieving an unknown key returns None."""
        result = get_parser("nonexistent")
        assert result is None


class TestIsEmpty:
    """Test is_empty function."""

    def test_is_empty_when_empty(self):
        """Test returns True when no parsers are registered."""
        assert is_empty() is True

    def test_is_empty_after_register(self):
        """Test returns False after registering a parser."""
        register_parser("mock_parser", MockParserFactory)

        assert is_empty() is False


class TestListParsers:
    """Test list_parsers and list_parsers_starting_with functions."""

    def test_list_all_parsers(self):
        """Test listing all registered parsers returns correct factories."""
        register_parser("mock_parser", MockParserFactory)
        register_parser("another_parser", AnotherMockParserFactory)

        result = list_parsers()
        assert len(result) == 2
        assert MockParserFactory in result
        assert AnotherMockParserFactory in result

    def test_list_starting_with_prefix(self):
        """Test filtering parsers by key prefix."""
        register_parser("cas_pdf", MockParserFactory)
        register_parser("cas_csv", AnotherMockParserFactory)
        register_parser("other_parser", MockParserFactory)

        result = list_parsers_starting_with("cas_")
        assert len(result) == 2
        keys = [key for key, _ in result]
        assert "cas_pdf" in keys
        assert "cas_csv" in keys

    def test_list_starting_with_no_match(self):
        """Test filtering with a prefix that matches nothing returns empty list."""
        register_parser("mock_parser", MockParserFactory)

        result = list_parsers_starting_with("zzz_")
        assert result == []


class TestDiscoverInstalledParsers:
    """Test discover_installed_parsers function."""

    def _make_mock_entry_points(self, entries):
        """Create a mock entry_points() return value supporting chained .select()."""
        mock_eps = MagicMock()

        def make_selectable(items):
            sel = MagicMock()
            sel.__iter__ = lambda self: iter(items)
            sel.select = lambda **kwargs: make_selectable(
                [
                    ep
                    for ep in items
                    if all(getattr(ep, k) == v for k, v in kwargs.items())
                ]
            )
            return sel

        mock_eps.select = lambda **kwargs: make_selectable(
            [
                ep
                for ep in entries
                if all(getattr(ep, k, None) == v for k, v in kwargs.items())
            ]
            if kwargs.get("group")
            else entries
        )
        # Initial select(group=...) should filter by group
        mock_eps.select = lambda **kwargs: make_selectable(entries)
        return mock_eps

    def test_discover_loads_entry_points(self):
        """Test that discover loads and registers entry point plugins."""
        mock_ep = MagicMock()
        mock_ep.name = "test_parser"
        mock_ep.load.return_value = MockParserFactory

        mock_eps = MagicMock()
        mock_eps.select.return_value = mock_eps
        mock_eps.__iter__ = lambda self: iter([mock_ep])

        with patch("importlib.metadata.entry_points", return_value=mock_eps):
            discover_installed_parsers()

        assert get_parser("test_parser") is MockParserFactory
        mock_ep.load.assert_called_once()

    def test_discover_with_name_filter(self):
        """Test that name parameter filters entry points via chained select."""
        mock_ep = MagicMock()
        mock_ep.name = "specific_parser"
        mock_ep.load.return_value = MockParserFactory

        # First select(group=...) returns an object, second select(name=...) filters further
        inner_eps = MagicMock()
        inner_eps.select.return_value = inner_eps
        inner_eps.__iter__ = lambda self: iter([mock_ep])

        outer_eps = MagicMock()
        outer_eps.select.return_value = inner_eps

        with patch("importlib.metadata.entry_points", return_value=outer_eps):
            discover_installed_parsers(name="specific_parser")

        assert get_parser("specific_parser") is MockParserFactory
        inner_eps.select.assert_called_once_with(name="specific_parser")

    def test_discover_clears_existing(self):
        """Test that discover clears previously registered parsers."""
        register_parser("old_parser", MockParserFactory)
        assert get_parser("old_parser") is MockParserFactory

        mock_eps = MagicMock()
        mock_eps.select.return_value = mock_eps
        mock_eps.__iter__ = lambda self: iter([])

        with patch("importlib.metadata.entry_points", return_value=mock_eps):
            discover_installed_parsers()

        assert get_parser("old_parser") is None
        assert is_empty() is True

    def test_discover_clears_cache(self):
        """Test that discover clears the list_parsers cache."""
        register_parser("cached_parser", MockParserFactory)
        # Prime the cache
        cached_result = list_parsers()
        assert len(cached_result) == 1

        mock_ep = MagicMock()
        mock_ep.name = "new_parser"
        mock_ep.load.return_value = AnotherMockParserFactory

        mock_eps = MagicMock()
        mock_eps.select.return_value = mock_eps
        mock_eps.__iter__ = lambda self: iter([mock_ep])

        with patch("importlib.metadata.entry_points", return_value=mock_eps):
            discover_installed_parsers()

        # Cache should be cleared; new call should reflect new state
        fresh_result = list_parsers()
        assert len(fresh_result) == 1
        assert AnotherMockParserFactory in fresh_result
