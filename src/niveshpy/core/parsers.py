"""Module for parser registration and management."""

import functools

from niveshpy.core.logging import logger
from niveshpy.models.parser import ParserFactory

_REGISTERED_PARSERS: dict[str, type[ParserFactory]] = {}


def register_parser(name: str, parser_factory: type[ParserFactory]) -> None:
    """Register a new parser."""
    parser_info = parser_factory.get_parser_info()
    if name in _REGISTERED_PARSERS:
        logger.warning(f"Parser with key '{name}' is already registered. Overwriting.")
    _REGISTERED_PARSERS[name] = parser_factory
    logger.info(f"Registered parser: {parser_info.name} ({name})")


def is_empty() -> bool:
    """Check if any parsers are registered."""
    return len(_REGISTERED_PARSERS) == 0


def get_parser(key: str) -> type[ParserFactory] | None:
    """Retrieve a registered parser by its key."""
    return _REGISTERED_PARSERS.get(key)


@functools.cache
def list_parsers_starting_with(prefix: str) -> list[tuple[str, type[ParserFactory]]]:
    """Retrieve registered parsers whose keys start with the given prefix."""
    return [
        (key, parser_factory)
        for key, parser_factory in _REGISTERED_PARSERS.items()
        if key.startswith(prefix)
    ]


@functools.cache
def list_parsers() -> list[type[ParserFactory]]:
    """List all registered parsers."""
    return list(_REGISTERED_PARSERS.values())


def discover_installed_parsers(name: str | None = None) -> None:
    """Discover and register all installed parsers."""
    import importlib.metadata

    _REGISTERED_PARSERS.clear()

    entry_points = importlib.metadata.entry_points()
    parser_entry_points = entry_points.select(group="niveshpy.parsers")

    if name:
        parser_entry_points = parser_entry_points.select(name=name)

    for entry_point in parser_entry_points:
        parser_factory = entry_point.load()
        register_parser(entry_point.name, parser_factory)
    list_parsers.cache_clear()
    list_parsers_starting_with.cache_clear()
