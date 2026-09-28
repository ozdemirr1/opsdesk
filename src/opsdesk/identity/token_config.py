from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class TokenSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="OPSDESK_JWT_",
        env_file=None,
        hide_input_in_errors=True,
        frozen=True,
    )

    secret: SecretStr

    @field_validator("secret")
    @classmethod
    def validate_secret(cls, value: SecretStr) -> SecretStr:
        secret = value.get_secret_value()

        try:
            encoded_secret = secret.encode("utf-8")
        except UnicodeEncodeError:
            raise ValueError("JWT secret is invalid.") from None

        if len(encoded_secret) < 32:
            raise ValueError("JWT secret must contain at least 32 UTF-8 bytes.")

        return value
