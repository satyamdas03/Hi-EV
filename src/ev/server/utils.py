"""Small shared helpers for the Hi-EV server package."""

from __future__ import annotations

from datetime import UTC, datetime


def _in_quiet_hours(start: str, end: str, now: datetime | None = None) -> bool:
    """Return True if `now` falls within the quiet-hours window.

    `start` and `end` are "HH:MM" strings. Windows that wrap midnight (e.g.
    22:00 -> 08:00) are handled correctly. Passing `now` makes the function
    deterministic in tests; when omitted it uses the current UTC time.
    """
    if now is None:
        now = datetime.now(UTC)
    now_t = now.time()
    start_t = datetime.strptime(start, "%H:%M").time()  # noqa: DTZ007
    end_t = datetime.strptime(end, "%H:%M").time()  # noqa: DTZ007
    if start_t < end_t:
        return start_t <= now_t <= end_t
    return now_t >= start_t or now_t <= end_t
