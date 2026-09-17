import json
import os
import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def _resolve_base_dir() -> Path:
    """数据/配置目录：打包后指向 exe 同级，开发时指向 backend/。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


BASE_DIR = _resolve_base_dir()


def _apply_json_preset() -> None:
    """在 Settings() 实例化之前，从 exe 同级 config.json 预置环境变量（零配置分发）。

    仅对「全大写且非空字符串」的键生效，且用 setdefault —— 真实环境变量优先级更高。
    """
    path = BASE_DIR / "config.json"
    if not path.is_file():
        return
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return
    if not isinstance(data, dict):
        return
    for k, v in data.items():
        if k.isupper() and isinstance(v, str) and v:
            os.environ.setdefault(k, v)


# ★ 必须在 Settings() 之前调用，否则 pydantic-settings 已经绑定环境变量
_apply_json_preset()

ENV_FILE = BASE_DIR / ".env"


def _default_db_url() -> str:
    """SQLite 单文件库（aiosqlite），存放于 BASE_DIR/data/。"""
    db_file = (BASE_DIR / "data" / "resumatch.db").resolve()
    return f"sqlite+aiosqlite:///{db_file.as_posix()}"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE) if ENV_FILE.is_file() else None,
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    APP_NAME: str = "ResuMatch AI"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = False

    # SQLite 单文件库（data/resumatch.db）
    DB_URL: str = _default_db_url()

    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""
    LLM_MODEL: str = ""


settings = Settings()
