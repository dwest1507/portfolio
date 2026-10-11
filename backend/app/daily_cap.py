"""The global daily request cap: a ceiling on what anonymous visitors can spend.

Generation calls a paid API (ADR-0008). The per-IP rate limit stops one visitor hammering
the endpoint, but not many visitors, or one with many addresses. This caps every chat
request together, per UTC day. Past it the endpoint still answers, with RESTING_MESSAGE,
so the visitor sees why rather than an error.

The count lives in memory: a restart or redeploy resets it, and each replica would keep
its own. With one Railway instance that is an acceptable ceiling, because the OpenAI
project's hard monthly budget is the backstop, not this.
"""

from collections.abc import Callable
from datetime import UTC, date, datetime

RESTING_MESSAGE = (
    "The assistant is resting for today — it has answered as many questions as it can "
    "until midnight UTC. Please come back tomorrow, or reach David directly through the "
    "contact links on this page."
)


def _utc_today() -> date:
    return datetime.now(UTC).date()


class DailyCap:
    """Admits up to `limit` requests per day, as told by `today` (UTC by default)."""

    def __init__(self, limit: int, today: Callable[[], date] = _utc_today):
        self.limit = limit
        self._today = today
        self._day: date | None = None
        self._count = 0

    def admit(self) -> bool:
        """Count one request; False once today's limit has been reached."""
        day = self._today()
        if day != self._day:
            self._day, self._count = day, 0
        if self._count >= self.limit:
            return False
        self._count += 1
        return True
