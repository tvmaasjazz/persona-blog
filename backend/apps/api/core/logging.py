import structlog

from apps.api.core.config import AppSettings
from apps.api.core.types import EnvironmentType


def configure_logging(app_settings: AppSettings) -> None:
    """Configures structlog, caching loggers on first use except in the test environment."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        cache_logger_on_first_use=app_settings.environment != EnvironmentType.TEST,
    )
