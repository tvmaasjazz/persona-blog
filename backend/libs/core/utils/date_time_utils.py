import time


class DateTimeUtils:
    """Measures durations on the monotonic clock, which never reaches the database."""

    @staticmethod
    def now_monotonic() -> float:
        """A reading of the monotonic clock, only meaningful next to another reading."""
        return time.perf_counter()

    @staticmethod
    def elapsed_ms(start_time: float) -> int:
        """Whole milliseconds since a now_monotonic() reading, rounded down."""
        return int((time.perf_counter() - start_time) * 1000)
