"""
构建指纹 / 作者标识工具

不要在业务代码里直接 import 作者信息，统一走这里。
"""
import hashlib


# 分散存放，需要时拼接
_PART_A = "xuconghui"
_PART_B = "03"
_PART_C = "@qq.com"


def get_author_email() -> str:
    """获取作者邮箱"""
    return f"{_PART_A}_{_PART_B}{_PART_C}"


def get_author_fingerprint() -> str:
    """获取作者指纹（短 hash）"""
    raw = f"{_PART_A}_{_PART_B}{_PART_C}".encode()
    return hashlib.md5(raw).hexdigest()[:12]


def get_build_tag() -> str:
    return "RM-2026-xuyi"