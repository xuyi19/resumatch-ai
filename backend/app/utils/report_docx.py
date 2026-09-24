# -*- coding: utf-8 -*-
"""诊断报告 Word 生成器（M20 A2）。

三段式结构：评分（综合分 + 六维表格）→ 差距（按维度分组）→ 建议（逐条改写对照）。
数据源为诊断记录的 result JSON（与报告页同源），不依赖前端传参。
"""
import io
from datetime import datetime

from docx import Document
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt, RGBColor

_INK = RGBColor(0x1F, 0x29, 0x37)
_SUB = RGBColor(0x5B, 0x63, 0x70)
_ACCENT = RGBColor(0x6D, 0x5D, 0xFC)
_BAD = RGBColor(0xE0, 0x4F, 0x52)
_WARN = RGBColor(0xC2, 0x83, 0x18)

_SEVERITY_TEXT = {"high": "高", "medium": "中", "low": "低"}

# 六维 key → 展示名（与前端 renderChart 保持一致）
_DIMENSIONS = [
    ("completeness", "信息完整"),
    ("quantification", "量化成果"),
    ("star_structure", "STAR 结构"),
    ("skill_match", "技能含金量"),
    ("achievement", "业绩亮点"),
    ("readability", "可读性"),
]


def _set_cell_shading(cell, hex_color: str):
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), hex_color)
    cell._tc.get_or_add_tcPr().append(shd)


def _style(doc: Document):
    style = doc.styles["Normal"]
    style.font.name = "Microsoft YaHei"
    style.font.size = Pt(10.5)
    style.font.color.rgb = _INK
    style.element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")
    for level, size in ((1, 14), (2, 12)):
        h = doc.styles[f"Heading {level}"]
        h.font.name = "Microsoft YaHei"
        h.font.size = Pt(size)
        h.font.color.rgb = _INK if level == 1 else _ACCENT
        h.element.rPr.rFonts.set(qn("w:eastAsia"), "Microsoft YaHei")


def _para(doc: Document, text: str, color=None, size=None, bold=False,
          align=None, space_after=6) -> None:
    p = doc.add_paragraph()
    p.paragraph_format.space_after = Pt(space_after)
    if align is not None:
        p.alignment = align
    run = p.add_run(text)
    run.bold = bold
    if color:
        run.font.color.rgb = color
    if size:
        run.font.size = Pt(size)
    return p


def generate_report_docx(result: dict) -> bytes:
    """把诊断 result JSON 渲染为报告 docx 字节流。"""
    diagnosis = (result or {}).get("diagnosis") or {}
    keyword = (result or {}).get("keyword") or "目标岗位"
    scores = diagnosis.get("scores") or {}
    overall = scores.get("overall", "--")

    doc = Document()
    _style(doc)

    # ---- 封面标题 ----
    _para(doc, "简历诊断报告", bold=True, size=22,
          align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    _para(
        doc,
        f"目标岗位：{keyword} · 生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        color=_SUB, size=9, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=14,
    )

    # ---- 第一段：评分 ----
    doc.add_heading("一、综合评分", level=1)
    _para(doc, f"{overall} / 100", color=_ACCENT, size=26, bold=True, space_after=2)

    doc.add_heading("六维评分明细", level=2)
    table = doc.add_table(rows=1, cols=3)
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    headers = ["维度", "得分", "评语"]
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        run = cell.paragraphs[0].add_run(h)
        run.bold = True
        run.font.color.rgb = _INK
        _set_cell_shading(cell, "EEF0FF")

    for key, name in _DIMENSIONS:
        item = scores.get(key) or {}
        row = table.add_row()
        row.cells[0].paragraphs[0].add_run(name)
        score = item.get("score")
        row.cells[1].paragraphs[0].add_run(str(score) if score is not None else "—")
        row.cells[2].paragraphs[0].add_run(str(item.get("comment", "")))
    doc.add_paragraph()

    # ---- 第二段：差距 ----
    doc.add_heading("二、待提升项", level=1)
    gaps = diagnosis.get("gaps") or []
    if diagnosis.get("gap_summary"):
        _para(doc, diagnosis["gap_summary"], color=_WARN)
    if gaps:
        # 按 dimension 分组（LLM 未给 dimension 时归入「其他」）
        groups: dict[str, list] = {}
        for g in gaps:
            groups.setdefault(str(g.get("dimension") or "其他"), []).append(g)
        for dim, items in groups.items():
            doc.add_heading(dim, level=2)
            for g in items:
                sev = _SEVERITY_TEXT.get(str(g.get("severity", "")).lower(), "")
                head = f"[{sev}] " if sev else ""
                p = _para(doc, f"{head}{g.get('description', '')}", bold=bool(sev))
                if sev == "高":
                    for run in p.runs:
                        run.font.color.rgb = _BAD
                elif sev == "中":
                    for run in p.runs:
                        run.font.color.rgb = _WARN
                for ev in g.get("evidence") or []:
                    text = str(ev.get("text", "")).strip()
                    if text:
                        _para(doc, f"依据 [{ev.get('id', '')}] {text}",
                              color=_SUB, size=9, space_after=2)
    else:
        _para(doc, "未发现明显差距。", color=_SUB)

    # ---- 第三段：建议 ----
    doc.add_heading("三、改写建议", level=1)
    suggestions = diagnosis.get("suggestions") or []
    for i, s in enumerate(suggestions, 1):
        doc.add_heading(f"建议 {i}：{s.get('target', '')}", level=2)
        original = str(s.get("original") or "").strip()
        if original:
            _para(doc, "原文：", color=_SUB, space_after=1)
            _para(doc, original, color=_SUB, space_after=4)
        rewritten = str(s.get("rewritten") or "").strip()
        if rewritten:
            _para(doc, "改写为：", color=_ACCENT, space_after=1)
            _para(doc, rewritten, bold=True, space_after=4)
        reason = str(s.get("reason") or "").strip()
        if reason:
            _para(doc, f"理由：{reason}", color=_SUB, size=9.5, space_after=8)

    if diagnosis.get("overall_advice"):
        doc.add_heading("整体建议", level=2)
        _para(doc, diagnosis["overall_advice"])

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def generate_interview_docx(payload: dict) -> bytes:
    """把面试会话数据渲染为报告 docx 字节流（M33）：问答记录 + 总评。

    payload: {questions: [{id, category, question}], answers: {qid: {answer, feedback}},
              summary: {overall, strengths, weaknesses, suggestions}}
    与页面同源（Conversation 表），不依赖前端传参。
    """
    questions = payload.get("questions") or []
    answers = payload.get("answers") or {}
    summary = payload.get("summary") or {}

    doc = Document()
    _style(doc)

    _para(doc, "模拟面试报告", bold=True, size=22,
          align=WD_ALIGN_PARAGRAPH.CENTER, space_after=2)
    _para(doc,
          f"共 {len(questions)} 题 · 生成于 {datetime.now().strftime('%Y-%m-%d %H:%M')}",
          color=_SUB, size=9, align=WD_ALIGN_PARAGRAPH.CENTER, space_after=14)

    # ---- 一、问答记录 ----
    doc.add_heading("一、面试问答记录", level=1)
    answered = 0
    for i, q in enumerate(questions, 1):
        doc.add_heading(f"第 {i} 题 · {q.get('category', '')}", level=2)
        _para(doc, str(q.get("question", "")), bold=True, space_after=6)
        item = answers.get(q.get("id")) or {}
        ans = str(item.get("answer") or "").strip()
        if ans:
            answered += 1
            _para(doc, "我的回答：", color=_SUB, space_after=1)
            _para(doc, ans, space_after=4)
        fb = str(item.get("feedback") or "").strip()
        if fb:
            _para(doc, "面试官点评：", color=_ACCENT, space_after=1)
            _para(doc, fb, space_after=8)
        if not ans:
            _para(doc, "（未作答）", color=_SUB, space_after=8)
    if not answered:
        _para(doc, "本场面试暂无作答记录。", color=_SUB)

    # ---- 二、总评 ----
    doc.add_heading("二、整体总评", level=1)
    overall = str(summary.get("overall") or "").strip()
    if overall:
        _para(doc, overall, space_after=8)
    for title, key, color in (
        ("亮点", "strengths", None),
        ("待改进", "weaknesses", _WARN),
        ("建议", "suggestions", _ACCENT),
    ):
        items = [str(x).strip() for x in (summary.get(key) or []) if str(x).strip()]
        if items:
            doc.add_heading(title, level=2)
            for x in items:
                _para(doc, f"• {x}", color=color, space_after=3)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
