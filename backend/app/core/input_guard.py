"""输入安全过滤模块（考核项四：提示词注入防护 + 违规内容拦截）。

设计目标：所有面向 LLM 的用户输入先过这一层，把「数据」与「指令」隔离的防线
前移到入口。三层过滤：
  1. 规范化与长度限制：去首尾空白、控制字符，超长截断；
  2. 提示词注入特征检测：中英文注入句式正则库（覆盖「忽略之前指令」「角色扮演
     越狱」「套取系统提示」等常见模式），命中即拦截；
  3. 违规内容词库拦截：政治敏感/暴力/色情等词库（示例级，可运营扩充）。

返回结构化结果（ok / reason / cleaned / flags），调用方据此 400 或放行，
拦截事件写入 loguru 日志留痕。
"""

from __future__ import annotations

import re

from loguru import logger

# 单条输入最大长度（防上下文撑爆与注入长文本堆叠）
MAX_INPUT_LEN = 8000

# 提示词注入特征（不区分大小写）。覆盖：指令覆盖 / 角色重置 / 越狱话术 /
# 系统提示套取 / 输出格式劫持 / 数据外带诱导 六类。
INJECTION_PATTERNS: list[tuple[str, re.Pattern]] = [
    ("指令覆盖-中", re.compile(r"(忽略|无视|忘记)[^。\n]{0,12}(之前|上面|以上|先前|前面)(的)?(所有|全部)?(指令|提示|规则|设定|要求)")),
    ("指令覆盖-英", re.compile(r"(ignore|disregard|forget)\s+(all\s+)?(previous|prior|above|earlier)\s+(instructions?|prompts?|rules?|constraints?)", re.I)),
    ("角色重置-中", re.compile(r"(从现在开始|现在开始|从即刻起)[^。\n]{0,10}(你|你将)(要|是|会)?(一个|一名)?(新的|不同的|无限制|不受限制)")),
    ("角色重置-英", re.compile(r"(you\s+are\s+now|act\s+as|pretend\s+to\s+be|behave\s+as)\s+(a\s+)?(different|new|unrestricted|uncensored|DAN)", re.I)),
    ("越狱话术", re.compile(r"(越狱|jailbreak|developer\s+mode|DAN\s+mode|do\s+anything\s+now|没有道德限制|不受任何限制)", re.I)),
    ("套取系统提示-中", re.compile(r"(输出|打印|重复|显示|告诉我)[^。\n]{0,8}(你的)?(系统提示|系统指令|初始指令|prompt|system\s*prompt)", re.I)),
    ("套取系统提示-英", re.compile(r"(reveal|print|repeat|show|output)\s+(your\s+)?(system\s+)?(prompt|instructions)", re.I)),
    ("输出格式劫持-中", re.compile(r"(直接|必须|请)?(输出|返回|给出)[^。\n]{0,6}(满分|100\s*分|100分|通过|合格)，?(不要|无需|跳过)[^。\n]{0,8}(分析|检查|评估|判断)")),
    ("输出格式劫持-英", re.compile(r"always\s+(say|output|respond)\s+.{0,20}(without|skip|no)\s+(analysis|checking|evaluation)", re.I)),
    ("数据外带-英", re.compile(r"(send|post|upload)\s+(the\s+)?(above|conversation|context)\s+to\s+https?://", re.I)),
]

# 违规内容词库（示例级：真实运营需接专业审核服务，此处演示入口拦截模式）
VIOLATION_WORDS: tuple[str, ...] = (
    "自杀教程", "制毒", "制爆", "枪支买卖", "赌博网站", "色情服务",
    "人身攻击辱骂文本生成", "仇恨言论生成",
)

# 控制字符（保留换行与制表）
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")


class GuardResult:
    """过滤结果：ok=放行；reason=拦截原因（ok 时为空）；flags=命中的特征名。"""

    __slots__ = ("ok", "reason", "cleaned", "flags")

    def __init__(self, ok: bool, reason: str, cleaned: str, flags: list[str]):
        self.ok = ok
        self.reason = reason
        self.cleaned = cleaned
        self.flags = flags


def sanitize_input(text: str | None, *, max_len: int = MAX_INPUT_LEN) -> GuardResult:
    """三层过滤入口：规范化 → 注入检测 → 违规词拦截。

    返回 GuardResult；拦截与放行均写日志（拦截带原因，供审计与调优）。
    """
    flags: list[str] = []

    # 1. 规范化与长度限制
    cleaned = _CTRL_RE.sub("", (text or "")).strip()
    if not cleaned:
        return GuardResult(False, "输入为空", "", flags)
    if len(cleaned) > max_len:
        cleaned = cleaned[:max_len]
        flags.append("长度截断")

    # 2. 提示词注入特征检测（命中即拦截——入口层宁严勿松，
    #    业务层另有 JD_INJECTION_GUARD 声明式防护作为第二道防线）
    for name, pattern in INJECTION_PATTERNS:
        if pattern.search(cleaned):
            flags.append(name)
            logger.warning(f"输入安全过滤·拦截[提示词注入:{name}]：{cleaned[:60]!r}...")
            return GuardResult(False, f"检测到疑似提示词注入内容（{name}），已拦截", cleaned, flags)

    # 3. 违规内容词库
    for word in VIOLATION_WORDS:
        if word in cleaned:
            flags.append(f"违规词:{word}")
            logger.warning(f"输入安全过滤·拦截[违规词:{word}]")
            return GuardResult(False, "输入包含违规内容，已拦截", cleaned, flags)

    if flags:
        logger.info(f"输入安全过滤·放行（规范化处理：{flags}）")
    return GuardResult(True, "", cleaned, flags)
