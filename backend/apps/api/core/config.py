from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

from apps.api.core.types import EnvironmentType


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        toml_file="config.toml",
        env_nested_delimiter="__",
    )

    app_name: str = "Persona Blog API"
    environment: EnvironmentType

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        toml_settings = TomlConfigSettingsSource(settings_cls)
        return (init_settings, env_settings, dotenv_settings, file_secret_settings, toml_settings)
