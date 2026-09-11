from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# backend/ 目录的绝对路径
BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_FILE = BASE_DIR / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    APP_NAME: str = "ResuMatch AI"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    DB_URL: str = "mysql+asyncmy://resumatch:Resumatch%402024@127.0.0.1:3306/resumatch?charset=utf8mb4"

    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""
    LLM_MODEL: str = ""


settings = Settings()