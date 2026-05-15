# Copilot Instructions for NiveshPy

NiveshPy is a Python CLI for managing mutual-fund portfolios (Indian markets).

## Build, Test, and Lint

Uses [uv](https://docs.astral.sh/uv/) for deps and [Hatch](https://hatch.pypa.io/) (VCS versioning) for builds.

```sh
uv sync --group dev                                  # install dev deps
uv run coverage run -m pytest                        # full test suite + coverage
uv run pytest tests/services/test_account_service.py # one file
uv run pytest -k "test_account_create"               # by name
uv run ruff check .                                  # lint
uv run ruff format --check .                         # format check
uv run ty check                                      # type check (NOT in pre-commit; manual / CI)
uv run mkdocs serve                                  # docs locally
```

Pre-commit hooks run **only** `ruff check` and `ruff format`. `ty check` is run separately.

## Architecture

```
CLI (Click)  →  Services            →  Repository Protocols          →  SQLite Repositories                       →  SqliteDatabase
(niveshpy/cli) (niveshpy/services)    (niveshpy/domain/repositories)    (niveshpy/infrastructure/sqlite/repositories) (infrastructure/sqlite/sqlite_db.py)
                                   ↘  Domain services (niveshpy/domain/services, pure logic, no I/O)
                                   ↘  Parsers / Providers (plugins via entry points)
```

- **CLI** ([niveshpy/cli/](niveshpy/cli/)): Click groups (`accounts`, `securities`, `transactions`, `parse`, `prices`, `reports`). Commands load on demand via `LazyGroup` / `LazyCommand` in [niveshpy/cli/utils/essentials.py](niveshpy/cli/utils/essentials.py).
- **Application container** ([niveshpy/core/app.py](niveshpy/core/app.py)): single `Application` class wires services to concrete sqlite repositories using `@functools.cached_property` + lazy imports. This is the source of truth for DI wiring — start here when tracing how a CLI command reaches the DB.
- **Services** ([niveshpy/services/](niveshpy/services/)): one per domain entity. Declared as `@dataclass(slots=True, frozen=True)` holding repository protocol deps. Methods accept `tuple[str, ...]` of query strings plus `limit`/`offset`, and translate them into filters via `get_prepared_filters_from_queries(queries, ast.Field.X)`. **Services never touch the DB directly** — they go through repositories.
- **Repository protocols** ([niveshpy/domain/repositories/](niveshpy/domain/repositories/)): `AccountRepository`, `SecurityRepository`, `TransactionRepository`, `PriceRepository` are `Protocol`s. Concrete SQLite impls live in [niveshpy/infrastructure/sqlite/repositories/](niveshpy/infrastructure/sqlite/repositories/) (`SqliteAccountRepository`, etc.).
- **Domain layer** ([niveshpy/domain/](niveshpy/domain/)): pure logic, no I/O. `domain/services/` (e.g., `LotAccountingService` for tax-lot accounting), `domain/models/` (value objects like `lot.py`).
- **Database** ([niveshpy/infrastructure/sqlite/sqlite_db.py](niveshpy/infrastructure/sqlite/sqlite_db.py)): raw `sqlite3` (no SQLModel/SQLAlchemy). Stored at `platformdirs.user_data_path("niveshpy") / "niveshpy.db"`. Registers a custom `iregexp` function and `PRAGMA foreign_keys=ON` per connection. Repositories use `with db.cursor() as cur:` — that context manager translates `sqlite3.IntegrityError → IntegrityError` and `sqlite3.Error → DatabaseError`. Migrations live under `infrastructure/sqlite/migrations/`.
- **Plugin system** ([niveshpy/core/parsers.py](niveshpy/core/parsers.py), [niveshpy/core/providers.py](niveshpy/core/providers.py)): parsers and providers are discovered via `importlib.metadata` entry points (`niveshpy.parsers`, `niveshpy.providers.price` in [pyproject.toml](pyproject.toml)). Each plugin implements `ParserFactory` / `ProviderFactory` ([niveshpy/models/parser.py](niveshpy/models/parser.py), [niveshpy/models/provider.py](niveshpy/models/provider.py)) and exposes `create_*` + `get_*_info`. Reference implementations: [niveshpy/parsers/cas.py](niveshpy/parsers/cas.py), [niveshpy/providers/amfi.py](niveshpy/providers/amfi.py).
- **Query language** ([niveshpy/core/query/](niveshpy/core/query/)): tokenizer → parser → AST for CLI filters like `name:foo`. Public entry: `get_prepared_filters_from_queries`.

## Key Conventions

- **Models** ([niveshpy/models/](niveshpy/models/)): plain `attrs @frozen` classes — typically just `FooCreate` (input) and `FooPublic` (output). **Not SQLModel**; there is no `Base` or `table=True` class. Repositories own the SQL/row mapping.
- **Result types** ([niveshpy/services/result.py](niveshpy/services/result.py)): use `InsertResult[T]` + `MergeAction` enum (`INSERT` / `UPDATE` / `NOTHING`) for upsert-style returns instead of ad-hoc tuples.
- **Custom exceptions** ([niveshpy/exceptions.py](niveshpy/exceptions.py)): hierarchical — `NiveshPyError` → category (`ValidationError`, `ResourceError`, `DatabaseError`, `NetworkError`, `OperationError`) → specific (e.g., `ResourceNotFoundError`, `AmbiguousResourceError`, `IntegrityError`, `QuerySyntaxError`, `InvalidInputError`). Always raise a domain-specific exception, never bare `Exception`.
- **Decimal precision**: financial amounts use `Decimal` — `NUMERIC(24, 2)` for amounts, `NUMERIC(24, 4)` for prices. Never use `float` for money.
- **CLI output**: use Rich (tables, errors, progress). Helpers in [niveshpy/cli/utils/output.py](niveshpy/cli/utils/output.py).
- **Docstrings**: Google style (ruff `D` with `convention = "google"`).
- **Ruff**: `E501` (line length) is ignored; `tests/*` may use `assert` (`S101` disabled).
- **Python**: 3.11+ (CI: 3.11, 3.12, 3.13). Use `|` unions, not `Union` / `Optional`.
- **Tests** ([tests/](tests/)): mirror the `niveshpy/` layout. [tests/conftest.py](tests/conftest.py) builds an in-memory `SqliteDatabase(db_path=Path(":memory:"))` and session-wide-mocks `platformdirs.user_data_path` so the real filesystem is never touched.

## Further Reading

| Topic | File |
|---|---|
| Architecture overview & decisions | [docs/architecture/index.md](docs/architecture/index.md), [docs/architecture/direction.md](docs/architecture/direction.md) |
| Authoring a parser plugin | [docs/advanced/parsers.md](docs/advanced/parsers.md) |
| Authoring a provider plugin | [docs/advanced/providers.md](docs/advanced/providers.md) |
| Query language reference | [docs/cli/queries.md](docs/cli/queries.md) |
