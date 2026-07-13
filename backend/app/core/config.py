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

    # TASK_STAGE1_v4.md, сессия 4: флаг для отката на старый generate_and_save_lesson
    # (lesson_generator.py) без правки кода — выключить и передеплоить.
    USE_NEW_LESSON_PIPELINE: bool = False

    # TASK_STAGE2.md, сессия 1: какой бэкенд использует НОВЫЙ пайплайн
    # (lesson_pipeline.py, через app/services/llm_client.py). Старый путь
    # (lesson_generator.py) всегда ходит в GigaChat напрямую, этот переключатель
    # его не касается. "gigachat" | "proxyapi".
    LLM_PROVIDER: str = "gigachat"
    PROXYAPI_KEY: str = ""
    PROXYAPI_MODEL: str = "claude-sonnet-5"


settings = Settings()
