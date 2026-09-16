from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OPSDESK_",
        env_file=None,
        hide_input_in_errors=True,
    )

    environment: Literal["development", "test", "production"] = "development"
    docs_enabled: bool = True
