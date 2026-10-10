# -*- coding: utf-8 -*-
"""简历 PDF 生成器（服务端真 PDF 导出）。

- 数据模型与 docx_generator 完全一致（编辑器 buildWordData 产物），Word/PDF 双轨同源
- 配色复用 docx_generator.TEMPLATES 模板色板：同一模板参数下两种格式观感一致
- 使用 pymupdf 内置 CJK 字体（china-s = Droid Sans Fallback，非嵌入引用）：
  零新增依赖、零字体文件、单份 PDF 仅几 KB
"""
from pathlib import Path

import pymupdf

from app.utils.docx_generator import TEMPLATES

PAGE_W, PAGE_H = 595.28, 841.89  # A4（pt）
MARGIN = 54.0
_FONT = "china-s"
_BODY_W = PAGE_W - MARGIN * 2
_GRAY = (0.45, 0.45, 0.45)


def _rgb(t: tuple) -> tuple:
    return tuple(c / 255.0 for c in t)


def _hex_rgb(h: str) -> tuple:
    h = (h or "E5E7EB").lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255.0 for i in (0, 2, 4))


def _is_word_char(ch: str) -> bool:
    return ch.isalnum() or ch in "._%+-/@#&"


def _wrap(font: pymupdf.Font, text: str, size: float, width: float) -> list[str]:
    """按实测宽度贪婪折行；ASCII 单词不从中间断开。"""
    lines: list[str] = []
    cur = ""
    for ch in text:
        if ch == "\n":
            lines.append(cur)
            cur = ""
            continue
        if cur and font.text_length(cur + ch, size) > width:
            # 行尾处于 ASCII 单词中间时把整个词挪到下一行
            m = 0
            while m < len(cur) and _is_word_char(cur[-1 - m]):
                m += 1
            if m and m < len(cur):
                lines.append(cur[:-m].rstrip())
                cur = cur[-m:]
                # 单词本身就超宽的极端场景：直接截断防死循环
                if font.text_length(cur + ch, size) > width:
                    lines.append(cur)
                    cur = ""
            else:
                lines.append(cur)
                cur = ""
        cur += ch
    if cur:
        lines.append(cur)
    return lines or [""]


def generate_resume_pdf(
    data: dict, template: str = "classic", photo_path: str | None = None
) -> bytes:
    """把优化后的简历渲染为 PDF 字节流。入参同 generate_resume_docx。"""
    tpl = TEMPLATES.get(template) or TEMPLATES["classic"]
    name_c, sect_c, text_c = _rgb(tpl["name_color"]), _rgb(tpl["section_color"]), _rgb(tpl["text_color"])
    line_c = _hex_rgb(tpl.get("line_color", "E5E7EB"))
    font = pymupdf.Font(_FONT)

    doc = pymupdf.open()
    state = {"page": None, "y": MARGIN}

    def _ensure(h: float) -> None:
        if state["page"] is None or state["y"] + h > PAGE_H - MARGIN:
            state["page"] = doc.new_page(width=PAGE_W, height=PAGE_H)
            state["y"] = MARGIN

    def _write(text: str, size: float, color, *, leading: float | None = None,
               indent: float = 0.0, max_width: float | None = None,
               gap_after: float = 0.0) -> None:
        leading = leading if leading is not None else size * 1.45
        width = min(_BODY_W - indent, max_width or _BODY_W)
        for ln in _wrap(font, str(text), size, width):
            _ensure(leading)
            state["page"].insert_text(
                (MARGIN + indent, state["y"] + size * 0.82), ln,
                fontname=_FONT, fontsize=size, color=color,
            )
            state["y"] += leading
        state["y"] += gap_after

    def _heading(title: str) -> None:
        _ensure(40)
        _write(title, 13, sect_c, gap_after=3)
        state["page"].draw_line(
            (MARGIN, state["y"] - 5), (PAGE_W - MARGIN, state["y"] - 5),
            color=line_c, width=0.8,
        )
        state["y"] += 8

    def _bullet(text: str) -> None:
        _write(f"• {text}", 10.5, text_c, indent=4, gap_after=1.5)

    # ---- 页眉：姓名 + 求职意向/联系方式（+ 右上角一寸照） ----
    photo_w = 0.0
    if photo_path and Path(photo_path).exists():
        pw, ph = 71.0, 99.0  # 一寸照 25×35mm
        rect = pymupdf.Rect(PAGE_W - MARGIN - pw, MARGIN, PAGE_W - MARGIN, MARGIN + ph)
        try:
            state["page"] = doc.new_page(width=PAGE_W, height=PAGE_H)
            state["y"] = MARGIN
            state["page"].insert_image(rect, filename=str(photo_path), keep_proportion=True)
            state["page"].draw_rect(rect, color=(0.75, 0.75, 0.75), width=0.7)
            photo_w = pw + 14
        except Exception:
            state["page"] = None  # 照片读取失败则退回纯文字页眉

    name = str(data.get("name") or "").strip() or "个人简历"
    _write(name, 20, name_c, max_width=_BODY_W - photo_w, gap_after=4)

    contacts = [str(s).strip() for s in (data.get("contacts") or []) if str(s).strip()]
    intention = str(data.get("job_intention") or "").strip()
    if intention and not any("求职意向" in s for s in contacts):
        contacts.append(f"求职意向：{intention}")
    if contacts:
        _write("  |  ".join(contacts), 9.5, _GRAY, max_width=_BODY_W - photo_w, gap_after=6)

    state["page"].draw_line(
        (MARGIN, state["y"] + 2), (PAGE_W - MARGIN, state["y"] + 2),
        color=line_c, width=1.2,
    )
    state["y"] += 14

    # ---- 正文区块（与 docx _render_body 语义一致） ----
    plan = [
        ("summary", "个人简介", [data.get("summary", "")], False),
        ("education", "教育经历", data.get("education", []), True),
        ("experience", "工作经历", data.get("experience", []), True),
        ("projects", "项目经历", data.get("projects", []), True),
    ]
    for _key, title, lines, bullet in plan:
        items = [str(x).strip() for x in (lines or []) if str(x).strip()]
        if not items:
            continue
        _heading(title)
        if bullet:
            for it in items:
                _bullet(it)
        else:
            _write(items[0], 10.5, text_c, gap_after=2)
        state["y"] += 6

    skills = [str(s).strip() for s in (data.get("skills") or []) if str(s).strip()]
    if skills:
        _heading("技能")
        _write(" · ".join(skills), 10.5, text_c, gap_after=2)

    certs = [str(c).strip() for c in (data.get("certificates") or []) if str(c).strip()]
    if certs:
        _heading("证书")
        for c in certs:
            _bullet(c)

    return doc.tobytes(garbage=3, deflate=True)
