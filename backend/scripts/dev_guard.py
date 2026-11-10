"""The check the dev scripts run first, so they never touch anything but a local dev database."""

from urllib.parse import urlparse

from apps.api.core.config import AppSettings
from apps.api.core.types import EnvironmentType

LOCAL_DATABASE_HOSTS = ("localhost", "127.0.0.1")


def refuse_outside_local_development(app_settings: AppSettings) -> None:
    """Exits with a message unless the environment is DEVELOPMENT and the database is local."""
    if app_settings.environment is not EnvironmentType.DEVELOPMENT:
        raise SystemExit(
            f"Refusing to run: environment is {app_settings.environment}, not DEVELOPMENT"
        )
    database_host = urlparse(app_settings.database_url).hostname
    if database_host not in LOCAL_DATABASE_HOSTS:
        raise SystemExit(f"Refusing to run: database host is {database_host}, not localhost")
