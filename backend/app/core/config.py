import json
import os
import sys
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# 版本单一事实源：app/__init__.py 的 __version__（env/config.json 仍可覆盖）
from app import __version__ as _APP_VERSION


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

    APP_NAME: str = "知岗 ResuMatch-AI"
    APP_VERSION: str = _APP_VERSION
    DEBUG: bool = False

    # 运行形态：local=桌面/本机单用户；web=线上部署（cookie 会话隔离 + 配额）
    APP_MODE: str = "local"

    # web 态匿名会话（HttpOnly cookie）
    SESSION_COOKIE: str = "rmsid"
    SESSION_TTL_DAYS: int = 30
    # web 态使用服务端 Key 时的每日诊断配额（用户自带 Key 不限）
    WEB_DAILY_LIMIT: int = 10

    # rewriter 后追加一轮自我批判精修（self-refine，多一次 LLM 调用换建议质量）
    ENABLE_SELF_REFINE: bool = True

    # SQLite 单文件库（data/resumatch.db）
    DB_URL: str = _default_db_url()

    # 证件照存放目录
    PHOTOS_DIR: str = str((BASE_DIR / "data" / "photos").resolve())

    # 简历原文件存放目录（上传的 PDF/DOCX 原件，供浏览器内原版式预览）
    FILES_DIR: str = str((BASE_DIR / "data" / "files").resolve())

    LLM_API_KEY: str = ""
    LLM_BASE_URL: str = ""
    LLM_MODEL: str = ""
    # 证据检索 embedding 模型（OpenAI /embeddings 协议）；留空默认
    # text-embedding-3-small，调用失败自动降级关键词检索
    LLM_EMBEDDING_MODEL: str = ""


settings = Settings()
