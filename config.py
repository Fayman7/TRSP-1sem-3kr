from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mode: Literal["DEV", "PROD"] = "DEV"
    docs_user: str = ""
    docs_password: str = ""

    @field_validator("mode", mode="before")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        normalized = str(value).upper()
        if normalized not in ("DEV", "PROD"):
            raise ValueError(f"Invalid MODE: {value!r}. Allowed values: DEV, PROD")
        return normalized


settings = Settings()
