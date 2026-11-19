from collections.abc import Callable
from datetime import UTC, datetime

# Services take a clock so tests control "now".
Clock = Callable[[], datetime]


def utc_now() -> datetime:
    return datetime.now(UTC)
