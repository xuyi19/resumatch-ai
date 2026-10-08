# -*- coding: utf-8 -*-
"""M71 统一导出目录与分类落盘。

桌面形态的所有导出产物（简历 Word / 投递材料包 / 面试报告 / 诊断报告 / 数据备份）
统一写入「导出根目录」下按类型划分的子目录，用户可在设置页查看与修改根目录；
网页形态维持浏览器 blob 下载，不落服务端磁盘。

根目录取值：app_settings(owner, key='export_root') > 默认 data/exports。
"""

from datetime import datetime
from pathlib import Path

from sqlalchemy import select

from app.core.config import settings

# app_settings 里的设置键
SETTING_KEY_EXPORT_ROOT = "export_root"


def default_export_root() -> Path:
    """导出根目录默认值：数据总目录（与 SQLite 库 / 证件照同级）下的 exports/。"""
    return Path(settings.DATA_DIR) / "exports"


# 导出分类：export_history.template → 导出根目录下的子目录名
# （report 为诊断报告在导出历史中的 template 值，与 diagnosis 同类）
_CLASS_DIRS = {
    "resume": "简历",
    "apply": "投递材料包",
    "interview": "面试报告",
    "diagnosis": "诊断报告",
    "report": "诊断报告",
    "backup": "数据备份",
}


def classify_dir(template: str) -> str:
    """导出模板 → 分类子目录名；未知模板归入「其他导出」。"""
    return _CLASS_DIRS.get((template or "").strip().lower(), "其他导出")


async def get_export_root(db, owner_id: str) -> tuple[Path, bool]:
    """生效导出根目录：(路径, 是否默认)。自定义值来自 app_settings（owner 隔离）。"""
    from app.models.entities import AppSetting

    res = await db.execute(
        select(AppSetting).where(
            AppSetting.owner_id == owner_id,
            AppSetting.key == SETTING_KEY_EXPORT_ROOT,
        )
    )
    rec = res.scalars().first()
    if rec and (rec.value or "").strip():
        return Path(rec.value.strip()), False
    return default_export_root(), True


def validate_root_path(raw: str) -> Path:
    """用户输入的导出根目录校验：非法字符抛 ValueError（路由转 422），相对路径绝对化。"""
    s = (raw or "").strip().strip('"')
    if not s:
        raise ValueError("路径不能为空")
    if any(c in s for c in '<>"|?*\0'):
        raise ValueError("路径包含非法字符")
    if ":" in s:
        # 仅允许盘符冒号（C:\...），其余位置的冒号一律非法
        head, _, tail = s.partition(":")
        if len(head) != 1 or tail[:1] not in ("\\", "/") or ":" in tail:
            raise ValueError("路径包含非法字符")
    p = Path(s)
    if not p.is_absolute():
        p = Path.cwd() / p
    try:
        return p.resolve()
    except (OSError, ValueError) as e:
        raise ValueError(f"路径无效：{e}")


def _dedupe(path: Path) -> Path:
    """同名文件防覆盖：追加 _2/_3…，超限退化为时间戳后缀。"""
    if not path.exists():
        return path
    for i in range(2, 1000):
        cand = path.with_name(f"{path.stem}_{i}{path.suffix}")
        if not cand.exists():
            return cand
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")
    return path.with_name(f"{path.stem}_{ts}{path.suffix}")


async def resolve_save_path(template: str, filename: str, db, owner_id: str) -> Path:
    """桌面形态统一落盘路径：导出根目录 / 分类子目录 / 文件名（重名自动避让）。"""
    root, _ = await get_export_root(db, owner_id)
    target_dir = root / classify_dir(template)
    target_dir.mkdir(parents=True, exist_ok=True)
    return _dedupe(target_dir / filename)
