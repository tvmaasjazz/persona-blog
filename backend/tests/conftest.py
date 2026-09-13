from collections.abc import Iterator

import pytest

from apps.api.core.config import AppSettings

TEST_ENVIRONMENT_VARIABLES = {
    "ENVIRONMENT": "test",
}


@pytest.fixture(scope="session", autouse=True)
def environment_variables() -> Iterator[None]:
    with pytest.MonkeyPatch.context() as session_monkeypatch:
        for variable_name, variable_value in TEST_ENVIRONMENT_VARIABLES.items():
            session_monkeypatch.setenv(variable_name, variable_value)
        yield


@pytest.fixture(scope="session")
def app_settings() -> AppSettings:
    return AppSettings()
