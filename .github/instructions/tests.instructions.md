---
applyTo: "tests/**"
description: NiveshPy test conventions — picking the right fixture and mock for the layer under test
---

# NiveshPy Test Conventions

Tests mirror the `niveshpy/` package layout. There are **three distinct test layers**, each with its own fixture pattern. Pick the one matching the layer you're testing — do not mix them.

## 1. Service tests — `tests/services/**`

Pure unit tests against `niveshpy/services/*`. Inject the `Mock*Repository` classes from [tests/services/conftest.py](tests/services/conftest.py); **never construct a `SqliteDatabase`** here.

```python
from niveshpy.services.account import AccountService
from tests.services.conftest import MockAccountRepository

@pytest.fixture
def account_service() -> AccountService:
    return AccountService(account_repository=MockAccountRepository())
```

- The mocks implement the same `domain/repositories/*` `Protocol` as the real SQLite repos, so service code is exercised unchanged.
- Group tests under `class TestMethodName:` (one class per service method) — see [tests/services/test_account_service.py](tests/services/test_account_service.py) for the canonical layout.
- If you add a new method to a repository protocol, **also add it to the matching `Mock*Repository`** in `tests/services/conftest.py`, or service tests will fail at runtime.

## 2. Repository / infrastructure tests — `tests/infrastructure/sqlite/**`

Use the `db` fixture from [tests/conftest.py](tests/conftest.py), which builds a fresh in-memory `SqliteDatabase(db_path=Path(":memory:"))` and runs migrations:

```python
def test_insert_account(db):
    repo = SqliteAccountRepository(db)
    ...
```

- One `db` per test (function scope) — do **not** share state across tests.
- Test SQL/row-mapping behavior here, not service logic.

## 3. CLI integration tests — `tests/cli/**`

Use the `cli_scenario` + `runner` fixtures from [tests/cli/conftest.py](tests/cli/conftest.py). The `cli_in_memory_db` autouse fixture monkeypatches `Application.db` to an in-memory database, so every `cli_scenario.invoke([...])` call hits a clean, isolated DB.

```python
def test_accounts_add(cli_scenario):
    account_id = cli_scenario.add_account("HDFC Savings", "HDFC Bank")
    accounts = cli_scenario.invoke_json(["accounts", "list"])
    assert accounts[0]["id"] == account_id
```

- Prefer the `CliScenario` helpers (`add_account`, `add_security`, `add_transaction`, `invoke_json`) over hand-rolling Click invocations — they assert exit codes and parse JSON output uniformly.
- Pass `--no-input` to commands that prompt; the runner won't supply stdin.
- Use `expected_exit_code=N` on `invoke()` for negative-path tests.

## General Conventions

- **Filesystem isolation**: the session-wide autouse `mock_platformdirs` fixture in [tests/conftest.py](tests/conftest.py) redirects `platformdirs.user_data_path` to `tmp_path_factory`. Never hit the real user data dir.
- **`assert` is allowed** in `tests/*` (ruff `S101` is disabled there). Plain `assert ...` is preferred over `unittest`-style asserts.
- **Naming**: `test_<module>.py` mirroring the source module (e.g., `niveshpy/services/account.py` → `tests/services/test_account_service.py`).
- **Decimal money**: in fixtures, pass amounts as strings (e.g., `"1000.50"`) so `Decimal` parsing is exercised. Never use `float`.
- **Exceptions**: assert against the specific subclass from [niveshpy/exceptions.py](niveshpy/exceptions.py) (e.g., `pytest.raises(InvalidInputError)`), not bare `Exception`.
- **Running tests**:
  ```sh
  uv run coverage run -m pytest                  # full suite
  uv run pytest tests/services/test_account_service.py::TestListAccounts
  uv run pytest -k "test_account_create"
  ```
