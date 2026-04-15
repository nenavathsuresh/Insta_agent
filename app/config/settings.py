from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
    )

    INSTAGRAM_ACCESS_TOKEN: str
    INSTAGRAM_USER_ID: str
    INSTAGRAM_PAGE_ID: str | None = None


settings = Settings()
