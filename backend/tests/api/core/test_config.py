from pathlib import Path

import pytest
from pydantic import ValidationError

from apps.api.core.config import AppSettings


def test_app_settings_toml_overrides_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_toml_path = tmp_path / "config.toml"
    config_toml_path.write_text('app_name = "From Toml"\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("APP_NAME", raising=False)

    loaded_app_settings = AppSettings()

    assert loaded_app_settings.app_name == "From Toml"


def test_app_settings_env_var_overrides_toml(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    config_toml_path = tmp_path / "config.toml"
    config_toml_path.write_text('app_name = "From Toml"\n')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("APP_NAME", "From Env")

    loaded_app_settings = AppSettings()

    assert loaded_app_settings.app_name == "From Env"


@pytest.mark.parametrize(
    "required_variable_name",
    [
        pytest.param("DATABASE_URL", id="database_url"),
        pytest.param("REDIS_URL", id="redis_url"),
    ],
)
def test_app_settings_missing_connection_url_raises_validation_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, required_variable_name: str
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv(required_variable_name)

    with pytest.raises(ValidationError):
        AppSettings()
