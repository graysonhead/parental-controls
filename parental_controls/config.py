from functools import cached_property

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    database_url: str = "sqlite:///./parental_controls.db"
    secret_key: str = "change-me-in-production"
    admin_pin: str = "0000"
    session_max_age: int = 3600  # seconds
    host: str = "127.0.0.1"
    port: int = 8000

    @cached_property
    def admin_pin_hash(self) -> str:
        from parental_controls.services.pin_service import hash_pin
        return hash_pin(self.admin_pin)


settings = Settings()
