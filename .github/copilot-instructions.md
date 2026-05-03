# Copilot Instructions for NiveshPy

## Build, Test, and Lint

This project uses [uv](https://docs.astral.sh/uv/) for dependency management and [Hatch](https://hatch.pypa.io/) as the build backend with VCS-based versioning.

```sh
# Install all dev dependencies
uv sync --group dev

# Run full test suite with coverage
uv run coverage run -m pytest

# Run a single test file
uv run pytest tests/models/test_account.py

# Run a single test by name
uv run pytest -k "test_account_create_with_required_fields"

# Lint and format
uv run ruff check .
uv run ruff format --check .

# Type checking
uv run ty check

# Build docs locally
uv run mkdocs serve
```

Pre-commit hooks run `ruff check`, `ruff format`, and `ty check` automatically.

## Architecture

NiveshPy is a financial CLI for managing mutual fund portfolios, targeted at Indian markets. It follows a layered architecture:

```
CLI (Click commands) → Services (business logic) → Database (SQLAlchemy/SQLite)
                                                  → Providers (external data)
                                                  → Parsers (file parsing)
```

- **CLI layer** (`niveshpy/cli/`): Click command groups (`accounts`, `securities`, `transactions`, `parse`, `prices`, `reports`). Uses a `LazyGroup`/`LazyCommand` pattern in `cli/utils/essentials.py` for on-demand loading.
- **Services layer** (`niveshpy/services/`): One service per domain entity. Services accept query strings, translate them into SQL filters via the query language, and use `database.session()` for DB access.
- **Models** (`niveshpy/models/`): SQLAlchemy models with a layered pattern — `FooBase` (shared fields) → `FooCreate` (input without ID) → `Foo(table=True)` (DB model) → `FooPublic` (output with ID). Domain models: `Account`, `Security`, `Transaction`, `Price`.
- **Parsers/Providers** (`niveshpy/parsers/`, `niveshpy/providers/`): Plugin system using Python entry points (`importlib.metadata`). Each plugin has a `Factory` class implementing a `Protocol` from `niveshpy/models/`. Discovered at runtime via `core/parsers.py` and `core/providers.py`.
- **Query language** (`niveshpy/core/query/`): Custom tokenizer → parser → AST for CLI filtering (e.g., `name:foo`).
- **Database** (`niveshpy/database.py`): SQLite via SQLAlchemy. Stored in `platformdirs.user_data_path("niveshpy")`. Registers a custom `iregexp` SQLite function and enables foreign keys on every connection.

## Key Conventions

- **Google-style docstrings** — enforced by ruff rule `D` with `convention = "google"`.
- **Model layering** — every domain model follows `Base → Create → Table → Public`. `Base` holds shared fields, `Create` is for input, `Table` (with `table=True`) is the DB model, `Public` is for output. Don't collapse these layers.
- **Custom exceptions** (`niveshpy/exceptions.py`) — hierarchical: `NiveshPyError` → category (`ValidationError`, `ResourceError`, `DatabaseError`, `NetworkError`, `OperationError`) → specific (e.g., `ResourceNotFoundError`, `QuerySyntaxError`). Always raise domain-specific exceptions, not bare `Exception`.
- **Plugin protocol** — parsers and providers are registered via entry points in `pyproject.toml` and must implement `ParserFactory` or `ProviderFactory` protocols. Use the factory pattern (`create_parser`/`create_provider` + `get_parser_info`/`get_provider_info`).
- **Session management** — always use `with database.session() as session:` OR `database.session.begin()` for database access. Never hold sessions across operations.
- **Decimal precision** — financial amounts use `Decimal` with explicit `NUMERIC(24, 2)` for amounts and `NUMERIC(24, 4)` for prices. Never use floats for money.
- **CLI output** — use Rich for formatting (tables, errors, progress). Output helpers are in `cli/utils/output.py`.
- **Ruff config** — `E501` (line length) is ignored. Tests are allowed to use `assert` (rule `S101` disabled for `tests/`).
- **Testing** — tests use an in-memory SQLite database (fixtures in `tests/conftest.py`). `platformdirs` is mocked session-wide to avoid touching the real filesystem. Tests are organized to mirror the `niveshpy/` package structure.
- **Python support** — 3.11+ (CI tests on 3.11, 3.12, 3.13). Use `|` union syntax over `Union`/`Optional`.
