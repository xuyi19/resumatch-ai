from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
    )

    APP_NAME: str = "ResuMatch AI"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True

    # 数据库
    DB_URL: str = "mysql+asyncmy://resumatch:Resumatch%402024@127.0.0.1:3306/resumatch?charset=utf8mb4"

    # 后续阶段用，先占位
    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""
    LLM_MODEL: str = ""


settings = Settings()