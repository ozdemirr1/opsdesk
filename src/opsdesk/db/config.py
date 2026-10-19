from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OPSDESK_DB_",
        env_file=None,
        hide_input_in_errors=True,
        frozen=True,
    )

    host: str = Field(min_length=1)
    port: int = Field(ge=1, le=65535)
    database: str = Field(min_length=1)
    username: str = Field(min_length=1)
    password: SecretStr = Field(min_length=1)
    connect_timeout_seconds: int = Field(default=5, ge=2, le=30)
    pool_timeout_seconds: int = Field(default=5, ge=1, le=30)


class IntegrationDatabaseSettings(DatabaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OPSDESK_TEST_DB_",
    )
