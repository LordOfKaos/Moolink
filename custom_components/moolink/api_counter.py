"""Daily count of requests made to the Bluelink cloud."""

from __future__ import annotations

import threading
from datetime import date
from typing import Any

from homeassistant.util import dt as dt_util

from .const import EU_DAILY_REQUEST_LIMIT, PIN_REQUIRED_REGIONS


class ApiRequestCounter:
    """Counts HTTP requests made through the library's session, per local day.

    The library makes its requests from executor threads, so the count is
    guarded by a lock and read back on the event loop.
    """

    def __init__(self, region: int) -> None:
        """Initialize the counter."""
        self._lock = threading.Lock()
        self._day: date = dt_util.now().date()
        self._count = 0
        # Hyundai doesn't publish limits; ~200/day is the figure reported for
        # Europe. Other regions have no well-known daily limit.
        self.daily_limit: int | None = (
            EU_DAILY_REQUEST_LIMIT if region in PIN_REQUIRED_REGIONS else None
        )

    def attach(self, session: Any) -> None:
        """Count every response the session receives."""
        hooks = getattr(session, "hooks", None)
        if hooks is not None:
            hooks.setdefault("response", []).append(self._on_response)

    def _on_response(self, response: Any, *args: Any, **kwargs: Any) -> Any:
        with self._lock:
            self._roll_over()
            self._count += 1
        return response

    def _roll_over(self) -> None:
        today = dt_util.now().date()
        if today != self._day:
            self._day = today
            self._count = 0

    @property
    def count(self) -> int:
        """Requests made today."""
        with self._lock:
            self._roll_over()
            return self._count

    @property
    def day(self) -> date:
        """The day the count belongs to."""
        with self._lock:
            self._roll_over()
            return self._day

    def restore(self, day: date, count: int) -> None:
        """Carry today's count over a Home Assistant restart."""
        with self._lock:
            self._roll_over()
            if day == self._day:
                self._count += count
