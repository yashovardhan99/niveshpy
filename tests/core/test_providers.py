"""Tests for provider registration and discovery."""

from unittest.mock import MagicMock, patch

import pytest

from niveshpy.core.providers import (
    discover_installed_providers,
    get_provider,
    is_empty,
    list_providers,
    list_providers_starting_with,
    register_provider,
)
from niveshpy.models.provider import ProviderInfo


class MockProviderFactory:
    """Mock provider factory satisfying the ProviderFactory protocol."""

    @classmethod
    def get_provider_info(cls):
        """Get mock provider info."""
        return ProviderInfo(name="Mock", description="Mock provider")

    @classmethod
    def create_provider(cls):
        """Create a mock provider."""
        return MagicMock()


class AnotherMockProviderFactory:
    """Second mock factory for multi-registration tests."""

    @classmethod
    def get_provider_info(cls):
        """Get another mock provider info."""
        return ProviderInfo(name="Another", description="Another mock provider")

    @classmethod
    def create_provider(cls):
        """Create another mock provider."""
        return MagicMock()


@pytest.fixture(autouse=True)
def clean_registry():
    """Clear provider registry and caches before and after each test."""
    from niveshpy.core import providers

    providers._REGISTERED_PROVIDERS.clear()
    providers.list_providers.cache_clear()
    providers.list_providers_starting_with.cache_clear()
    yield
    providers._REGISTERED_PROVIDERS.clear()
    providers.list_providers.cache_clear()
    providers.list_providers_starting_with.cache_clear()


class TestRegisterProvider:
    """Test register_provider function."""

    def test_register_new_provider(self):
        """Test registering a new provider adds it to the registry."""
        register_provider("mock_provider", MockProviderFactory)

        assert get_provider("mock_provider") is MockProviderFactory

    def test_register_overwrites_existing(self):
        """Test registering with the same key overwrites the previous factory."""
        register_provider("mock_provider", MockProviderFactory)
        register_provider("mock_provider", AnotherMockProviderFactory)

        assert get_provider("mock_provider") is AnotherMockProviderFactory


class TestGetProvider:
    """Test get_provider function."""

    def test_get_registered_provider(self):
        """Test retrieving a registered provider returns the correct factory."""
        register_provider("mock_provider", MockProviderFactory)

        result = get_provider("mock_provider")
        assert result is MockProviderFactory

    def test_get_unregistered_returns_none(self):
        """Test retrieving an unknown key returns None."""
        result = get_provider("nonexistent")
        assert result is None


class TestIsEmpty:
    """Test is_empty function."""

    def test_is_empty_when_empty(self):
        """Test returns True when no providers are registered."""
        assert is_empty() is True

    def test_is_empty_after_register(self):
        """Test returns False after registering a provider."""
        register_provider("mock_provider", MockProviderFactory)

        assert is_empty() is False


class TestListProviders:
    """Test list_providers and list_providers_starting_with functions."""

    def test_list_all_providers(self):
        """Test listing all registered providers returns correct tuples."""
        register_provider("mock_provider", MockProviderFactory)
        register_provider("another_provider", AnotherMockProviderFactory)

        result = list_providers()
        assert len(result) == 2
        result_dict = dict(result)
        assert result_dict["mock_provider"] is MockProviderFactory
        assert result_dict["another_provider"] is AnotherMockProviderFactory

    def test_list_starting_with_prefix(self):
        """Test filtering providers by key prefix."""
        register_provider("amfi_v1", MockProviderFactory)
        register_provider("amfi_v2", AnotherMockProviderFactory)
        register_provider("other_provider", MockProviderFactory)

        result = list_providers_starting_with("amfi_")
        assert len(result) == 2
        keys = [key for key, _ in result]
        assert "amfi_v1" in keys
        assert "amfi_v2" in keys

    def test_list_starting_with_no_match(self):
        """Test filtering with a prefix that matches nothing returns empty list."""
        register_provider("mock_provider", MockProviderFactory)

        result = list_providers_starting_with("zzz_")
        assert result == []


class TestDiscoverInstalledProviders:
    """Test discover_installed_providers function."""

    def test_discover_loads_entry_points(self):
        """Test that discover loads and registers entry point plugins."""
        mock_ep = MagicMock()
        mock_ep.name = "test_provider"
        mock_ep.load.return_value = MockProviderFactory

        mock_eps = MagicMock()
        mock_eps.select.return_value = mock_eps
        mock_eps.__iter__ = lambda self: iter([mock_ep])

        with patch("importlib.metadata.entry_points", return_value=mock_eps):
            discover_installed_providers()

        assert get_provider("test_provider") is MockProviderFactory
        mock_ep.load.assert_called_once()

    def test_discover_with_name_filter(self):
        """Test that name parameter filters entry points via chained select."""
        mock_ep = MagicMock()
        mock_ep.name = "specific_provider"
        mock_ep.load.return_value = MockProviderFactory

        inner_eps = MagicMock()
        inner_eps.select.return_value = inner_eps
        inner_eps.__iter__ = lambda self: iter([mock_ep])

        outer_eps = MagicMock()
        outer_eps.select.return_value = inner_eps

        with patch("importlib.metadata.entry_points", return_value=outer_eps):
            discover_installed_providers(name="specific_provider")

        assert get_provider("specific_provider") is MockProviderFactory
        inner_eps.select.assert_called_once_with(name="specific_provider")

    def test_discover_clears_existing(self):
        """Test that discover clears previously registered providers."""
        register_provider("old_provider", MockProviderFactory)
        assert get_provider("old_provider") is MockProviderFactory

        mock_eps = MagicMock()
        mock_eps.select.return_value = mock_eps
        mock_eps.__iter__ = lambda self: iter([])

        with patch("importlib.metadata.entry_points", return_value=mock_eps):
            discover_installed_providers()

        assert get_provider("old_provider") is None
        assert is_empty() is True

    def test_discover_clears_cache(self):
        """Test that discover clears the list_providers cache."""
        register_provider("cached_provider", MockProviderFactory)
        # Prime the cache
        cached_result = list_providers()
        assert len(cached_result) == 1

        mock_ep = MagicMock()
        mock_ep.name = "new_provider"
        mock_ep.load.return_value = AnotherMockProviderFactory

        mock_eps = MagicMock()
        mock_eps.select.return_value = mock_eps
        mock_eps.__iter__ = lambda self: iter([mock_ep])

        with patch("importlib.metadata.entry_points", return_value=mock_eps):
            discover_installed_providers()

        # Cache should be cleared; new call should reflect new state
        fresh_result = list_providers()
        assert len(fresh_result) == 1
        result_dict = dict(fresh_result)
        assert result_dict["new_provider"] is AnotherMockProviderFactory
