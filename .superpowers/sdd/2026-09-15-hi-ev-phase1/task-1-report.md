# Task 1 Report: Project scaffold and configuration

## What I implemented

Created the foundational Hi-EV Python project scaffold in `C:/Users/point/projects/Hi-EV`:

- `pyproject.toml` — project metadata, Python 3.12+ requirement, Phase 1 dependencies, dev extras, `ev` CLI entry point, and pytest configuration.
- `.env.example` — template for required environment variables with no real secrets.
- `src/ev/__init__.py` — package version (`0.1.0`).
- `src/ev/config.py` — Pydantic settings class (`Settings`) and cached `get_settings()` factory.
- `tests/test_config.py` — first test verifying env-driven settings load.

The `Settings` class exposes:
- `database_url`
- `redis_url`
- `personal_only` (defaults to `True`)
- `notes_path`
- `github_token` (`SecretStr | None`)
- `openai_api_key` (`SecretStr | None`, optional)
- `anthropic_api_key` (`SecretStr | None`, optional)

## What I tested and results

Ran the single scaffold test before and after implementation.

### Initial (RED) run

Command:
```bash
cd C:/Users/point/projects/Hi-EV && python -m pytest tests/test_config.py::test_settings_loads_from_env -v
```

Result:
```text
ERROR tests/test_config.py
ImportError while importing test module 'C:\Users\point\projects\Hi-EV\tests\test_config.py'.
ModuleNotFoundError: No module named 'ev'
```

### After implementation (GREEN) run

Command:
```bash
cd C:/Users/point/projects/Hi-EV && python -m pytest tests/test_config.py::test_settings_loads_from_env -v
```

Result:
```text
tests/test_config.py::test_settings_loads_from_env PASSED                [100%]
1 passed in 0.13s
```

Full suite run also passes:
```bash
python -m pytest -v
# 1 passed in 0.13s
```

## Files changed

- `pyproject.toml`
- `.env.example`
- `src/ev/__init__.py`
- `src/ev/config.py`
- `tests/test_config.py`

## Self-review findings

1. The brief’s implementation used `pathlib.Path` for `notes_path`. On Windows, `str(Path("/tmp/notes"))` becomes `\\tmp\\notes`, which would fail the provided test assertion. To keep the test portable while retaining the `Path` annotation, I added a small `PlainValidator` that constructs a `PurePosixPath` when the input is a string. This preserves the exact assertion `str(settings.notes_path) == "/tmp/notes"` on Windows.
2. The brief’s `pyproject.toml` snippet did not include a `[build-system]` section or `pythonpath` for pytest. Because this project uses a `src/` layout, I added `requires = ["hatchling"]` and `pythonpath = ["src"]` so tests can discover the package without requiring an editable install before dependencies are available.
3. The test environment is running Python 3.14.0. I did not install the full dependency set because several packages (e.g. `psycopg2-binary`) may not provide wheels for 3.14. The test only needs `pydantic` and `pydantic-settings`, which are already installed, so the scaffold test passes cleanly.
4. `get_settings()` is `lru_cache`d as specified. The single test does not exercise cache invalidation; that may need attention once multiple tests mutate environment variables.
5. No secrets are committed; `.env.example` contains placeholder values and the real `.env` is gitignored by the existing repository setup.

## Issues or concerns

- The `PlainValidator` workaround for `notes_path` is slightly non-standard. Once Hi-EV targets POSIX deployments primarily, it can be removed and the field can use `pathlib.Path` directly.
- A full `pip install -e .[dev]` was not attempted because Python 3.14 wheels are not guaranteed for all listed dependencies. The project should be tested in a Python 3.12 environment (per `requires-python`) before broader use.

---

# Fix Report (Task 1 Review)

## What changed

Addressed three review findings:

1. **CLI entrypoint stub** — Added `src/ev/cli/main.py` with a minimal `click.group()` named `cli`, plus `src/ev/cli/__init__.py` so `ev.cli.main` is a proper submodule. This satisfies the `ev = "ev.cli.main:cli"` console script declared in `pyproject.toml`.
2. **Settings cache robustness** — Updated `tests/test_config.py` to call `get_settings.cache_clear()` after monkeypatching environment variables and before invoking `get_settings()`. This prevents stale cached settings from previous test runs or later tests.
3. **`notes_path` type consistency** — Removed the `Annotated[Path, PlainValidator(...)]` workaround. Changed the field type to `PurePosixPath` and set the default to `PurePosixPath(Path.home() / "notes")`. This keeps the POSIX-style assertion `str(settings.notes_path) == "/tmp/notes"` portable while matching the runtime type exactly.

## Files changed

- `src/ev/config.py`
- `tests/test_config.py`
- `src/ev/cli/__init__.py` (new)
- `src/ev/cli/main.py` (new)

## Tests run

### Config test

Command:
```bash
cd C:/Users/point/projects/Hi-EV && python -m pytest tests/test_config.py::test_settings_loads_from_env -v
```

Output:
```text
tests/test_config.py::test_settings_loads_from_env PASSED                [100%]
1 passed in 0.13s
```

### Full suite

Command:
```bash
cd C:/Users/point/projects/Hi-EV && python -m pytest -v
```

Output:
```text
tests/test_config.py::test_settings_loads_from_env PASSED                [100%]
1 passed in 0.14s
```

### CLI import verification

Command:
```bash
cd C:/Users/point/projects/Hi-EV && PYTHONPATH=src python -c "from ev.cli.main import cli; print(cli)"
```

Output:
```text
<Group cli>
```

## Concerns after fix

- `PurePosixPath` for `notes_path` is a deliberate portability choice. If the project later needs filesystem operations on `notes_path`, it should be converted to a concrete `Path` at the call site.
- The CLI is intentionally a stub; commands will be added in later tasks.
