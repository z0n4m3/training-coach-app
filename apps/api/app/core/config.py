from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    database_url: str = "postgresql+psycopg://training:training@localhost:5432/training"
    intervals_base_url: str = "https://intervals.icu/api/v1"
    intervals_api_key: str = ""
    intervals_athlete_id: str = "0"
    duplicate_auto_merge_threshold: float = 0.90
    duplicate_review_threshold: float = 0.70

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
