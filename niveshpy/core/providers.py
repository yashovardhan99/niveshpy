"""Module for provider registration and management."""

import functools

from niveshpy.core.logging import logger
from niveshpy.models.provider import ProviderFactory

_REGISTERED_PROVIDERS: dict[str, type[ProviderFactory]] = {}


def register_provider(name: str, provider_factory: type[ProviderFactory]) -> None:
    """Register a new provider."""
    provider_info = provider_factory.get_provider_info()
    if name in _REGISTERED_PROVIDERS:
        logger.warning(
            f"Provider with key '{name}' is already registered. Overwriting."
        )
    _REGISTERED_PROVIDERS[name] = provider_factory
    logger.info(f"Registered provider: {provider_info.name} ({name})")


def is_empty() -> bool:
    """Check if any providers are registered."""
    return len(_REGISTERED_PROVIDERS) == 0


def get_provider(key: str) -> type[ProviderFactory] | None:
    """Retrieve a registered provider by its key."""
    return _REGISTERED_PROVIDERS.get(key)


@functools.cache
def list_providers_starting_with(
    prefix: str,
) -> list[tuple[str, type[ProviderFactory]]]:
    """Retrieve registered providers whose keys start with the given prefix."""
    return [
        (key, provider_factory)
        for key, provider_factory in _REGISTERED_PROVIDERS.items()
        if key.startswith(prefix)
    ]


@functools.cache
def list_providers() -> list[tuple[str, type[ProviderFactory]]]:
    """List all registered providers."""
    return list(_REGISTERED_PROVIDERS.items())


def discover_installed_providers(name: str | None = None) -> None:
    """Discover and register all installed providers."""
    import importlib.metadata

    _REGISTERED_PROVIDERS.clear()

    entry_points = importlib.metadata.entry_points()
    provider_entry_points = entry_points.select(group="niveshpy.providers.price")

    if name:
        provider_entry_points = provider_entry_points.select(name=name)

    for entry_point in provider_entry_points:
        provider_factory = entry_point.load()
        register_provider(entry_point.name, provider_factory)

    list_providers.cache_clear()
    list_providers_starting_with.cache_clear()
