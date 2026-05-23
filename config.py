from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    mode: Literal["DEV", "PROD"] = "DEV"
    docs_user: str = ""
    docs_password: str = ""
    jwt_secret: str = "your-secret-key"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 30

    @field_validator("mode", mode="before")
    @classmethod
    def validate_mode(cls, value: str) -> str:
        normalized = str(value).upper()
        if normalized not in ("DEV", "PROD"):
            raise ValueError(f"Invalid MODE: {value!r}. Allowed values: DEV, PROD")
        return normalized


settings = Settings()
