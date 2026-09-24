"""pytest 共享夹具：ASGITransport 不触发 lifespan，测试前手动建表 + 老库补列。

测试隔离：DB 与证件照目录都改指 tests/.tmp/，不污染开发库与运行时 data/ 目录。
环境变量必须在导入任何 app 模块之前设置——app.core.config 在导入时即实例化 settings，
app.core.db 紧接着按 DB_URL 建好引擎，之后再改就来不及了。
"""
import os
from pathlib import Path

_TMP_DIR = Path(__file__).resolve().parent / ".tmp"
_TMP_DIR.mkdir(parents=True, exist_ok=True)
# 直接赋值而非 setdefault：测试绝不允许写进开发库（config.json 预置用的是 setdefault，不会覆盖这里）
os.environ["DB_URL"] = f"sqlite+aiosqlite:///{(_TMP_DIR / 'test.db').as_posix()}"
os.environ["PHOTOS_DIR"] = str(_TMP_DIR / "photos")
os.environ["FILES_DIR"] = str(_TMP_DIR / "files")  # 简历原文件（PDF/DOCX 预览）

# M16：SqliteSaver 快照库（checkpoints.db）跨 pytest 运行留存，同 thread_id 的
# 图状态会携带上次运行的 channel 残留（如已完成运行的 suggestions），先清空
for _stale in _TMP_DIR.glob("checkpoints.db*"):
    _stale.unlink(missing_ok=True)

import pytest  # noqa: E402
import pytest_asyncio  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.db import Base, ensure_schema_columns, engine  # noqa: E402
from app.models import entities  # noqa: F401,E402 注册 ORM 模型

# 自检：隔离未生效就立刻失败，避免静默写进开发库
assert Path(settings.DB_URL.split("///", 1)[1]).is_relative_to(_TMP_DIR), (
    f"测试库未隔离到 tests/.tmp/，当前为 {settings.DB_URL}"
)


@pytest_asyncio.fixture(autouse=True)
async def _create_tables():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await ensure_schema_columns()
    yield
