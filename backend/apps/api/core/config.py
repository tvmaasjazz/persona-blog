from pydantic import Field
from pydantic_settings import (
    BaseSettings,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

from apps.api.core.types import EnvironmentType
from libs.auth.settings import AuthSettings
from libs.core.settings import BackgroundJobSettings
from libs.generate_text.settings import GenerateTextSettings
from libs.google_auth.settings import GoogleAuthSettings
from libs.llm.settings import LlmSettings
from libs.users.settings import UserSettings


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        toml_file="config.toml",
        env_file=".env",
        env_nested_delimiter="__",
    )

    app_name: str = "Persona Blog API"
    environment: EnvironmentType
    database_url: str
    redis_url: str
    google_client_id: str
    google_client_secret: str
    openai_api_key: str = Field(min_length=1)
    railway_replica_id: str | None = None
    auth: AuthSettings = Field(default_factory=AuthSettings)
    background_jobs: BackgroundJobSettings = Field(default_factory=BackgroundJobSettings)
    generate_text: GenerateTextSettings = Field(default_factory=GenerateTextSettings)
    google_auth: GoogleAuthSettings = Field(default_factory=GoogleAuthSettings)
    llm: LlmSettings = Field(default_factory=LlmSettings)
    users: UserSettings = Field(default_factory=UserSettings)

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
