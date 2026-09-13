import structlog

from apps.api.core.config import AppSettings

TEST_ENVIRONMENT = "test"


def configure_logging(app_settings: AppSettings) -> None:
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.dev.ConsoleRenderer(),
        ],
        cache_logger_on_first_use=app_settings.environment != TEST_ENVIRONMENT,
    )
