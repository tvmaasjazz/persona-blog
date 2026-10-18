import time
from datetime import UTC, datetime, timedelta


class DateTimeUtils:
    @staticmethod
    def now_monotonic() -> float:
        return time.perf_counter()

    @staticmethod
    def elapsed_ms(start_time: float) -> int:
        return int((time.perf_counter() - start_time) * 1000)

    @staticmethod
    def seconds_from_now(seconds: float) -> datetime:
        return datetime.now(UTC) + timedelta(seconds=seconds)
