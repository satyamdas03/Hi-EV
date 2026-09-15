# Task 3 Report: Security boundary — personal-only and blocklist

## What I implemented

Created the `ev.security` package with a minimal, deterministic guard layer:

- `src/ev/security/boundary.py`
  - `PersonalOnlyError` exception.
  - `assert_personal_only(config)` — raises `PersonalOnlyError` when `config.personal_only` is `False`.
  - `personal_only_guard(config)` — context manager that runs `assert_personal_only` before yielding.
  - `Blocklist` class with:
    - `is_blocked_repo(url_or_name)` — blocks if any configured work handle appears in the string.
    - `is_blocked_account(handle_or_email)` — blocks if any work domain or work handle appears in the string.
- `src/ev/security/__init__.py` — re-exports the public API.
- `tests/test_security.py` — three TDD tests covering `assert_personal_only`, `Blocklist`, and `personal_only_guard`.

## What I tested and test results

Ran the security tests before and after implementation:

**RED (before implementation):**
```
pytest tests/test_security.py -v
ERROR tests/test_security.py
ModuleNotFoundError: No module named 'ev.security'
1 error in 0.42s
```

**GREEN (after implementation):**
```
pytest tests/test_security.py -v
tests/test_security.py::test_assert_personal_only_raises_when_false PASSED
tests/test_security.py::test_blocklist_flags_work_repos PASSED
tests/test_security.py::test_personal_only_guard_accepts_true PASSED
3 passed in 0.08s
```

Also ran the non-DB test subset to ensure no regressions:

```
pytest tests/test_security.py tests/test_config.py -v
4 passed in 0.09s
```

Linting passed:

```
ruff check src/ev/security tests/test_security.py
All checks passed!
```

## Files changed

- `src/ev/security/__init__.py` (new)
- `src/ev/security/boundary.py` (new)
- `tests/test_security.py` (new)

## TDD Evidence

- RED command: `pytest tests/test_security.py -v`
  - Output: `ModuleNotFoundError: No module named 'ev.security'`
- GREEN command: `pytest tests/test_security.py -v`
  - Output: `3 passed in 0.08s`

## Self-review findings

- The implementation exactly matches the brief interfaces.
- `assert_personal_only` correctly consumes `ev.config.Settings.personal_only`.
- `Blocklist` uses case-insensitive substring matching, which is simple and deterministic.
- The unused `urlparse` import from the draft brief was removed to keep `ruff` clean; substring checking does not require URL parsing.
- One minor design note: `is_blocked_repo` currently checks only `work_handles`, not `work_domains`. This matches the brief, but future tasks may want domain-based repo blocking as well.

## Issues or concerns

- The full `pytest` suite currently fails to collect because `tests/test_db.py` imports `sqlalchemy`, which is not installed in the active environment. This is pre-existing and unrelated to Task 3; the task-specific tests all pass.
