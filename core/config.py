from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    GITHUB_TOKEN: str = ""
    GITHUB_MODELS_TOKEN: str = ""
    ALLOWED_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5173"]


settings = Settings()
