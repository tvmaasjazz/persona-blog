import time


class DateTimeUtils:
    @staticmethod
    def now_monotonic() -> float:
        return time.perf_counter()

    @staticmethod
    def elapsed_ms(start_time: float) -> int:
        return int((time.perf_counter() - start_time) * 1000)
