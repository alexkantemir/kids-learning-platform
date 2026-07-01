from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str
    REDIS_URL: str = "redis://redis:6379"
    SECRET_KEY: str
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    GIGACHAT_CLIENT_ID: str
    GIGACHAT_CLIENT_SECRET: str
    GIGACHAT_SCOPE: str = "GIGACHAT_API_PERS"

    ENVIRONMENT: str = "production"


settings = Settings()
