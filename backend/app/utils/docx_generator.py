# -*- coding: utf-8 -*-
"""简历 Word 生成器（多模板 + 证件照支持）。

模板体系：
- 全部模板支持右上角一寸照（表格式页眉，无照片时保持原有纯文字页眉）
- 新增 sidebar（左侧信息栏双栏）与 elegant（衬线+金色点缀）两套布局
- 统一渲染器处理 正文区块（简介/教育/工作/项目），证书区块全模板支持
"""
import io
import re

from docx import Document
from docx.enum.table import WD_ALIGN_VERTICAL
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, RGBColor

TEMPLATES = {
    "classic": {
        "name_color": (0x1F, 0x29, 0x37),
        "section_color": (0x0D, 0x94, 0x88),
        "text_color": (0x37, 0x41, 0x51),
        "line_color": "E5E7EB",
    },
    "modern": {
        "name_color": (0x0F, 0x17, 0x2A),
        "section_color": (0x14, 0xB8, 0xA6),
        "text_color": (0x33, 0x33, 0x33),
        "line_color": "14B8A6",
    },
    "minimal": {
        "name_color": (0x00, 0x00, 0x00),
        "section_color": (0x66, 0x66, 0x66),
        "text_color": (0x33, 0x33, 0x33),
        "line_color": "EEEEEE",
    },
    "business": {
        "name_color": (0x0C, 0x29, 0x4E),
        "section_color": (0x1E, 0x40, 0xAF),
        "text_color": (0x1F, 0x29, 0x37),
        "line_color": "1E40AF",
    },
    "academic": {
        "name_color": (0x00, 0x00, 0x00),
        "section_color": (0x44, 0x44, 0x44),
        "text_color": (0x22, 0x22, 0x22),
        "line_color": "999999",
    },
    "creative": {
        "name_color": (0x7C, 0x2D, 0x12),
        "section_color": (0xC2, 0x41, 0x0C),
        "text_color": (0x44, 0x44, 0x44),
        "line_color": "FED7AA",
    },
    "twocol": {
        "name_color": (0x1F, 0x29, 0x37),
        "section_color": (0x0D, 0x94, 0x88),
        "text_color": (0x37, 0x41, 0x51),
        "line_color": "E5E7EB",
    },
    "compact": {
        "name_color": (0x00, 0x00, 0x00),
        "section_color": (0x00, 0x00, 0x00),
        "text_color": (0x33, 0x33, 0x33),
        "line_color": "CCCCCC",
    },
    "elegant": {
        "name_color": (0x1A, 0x1A, 0x1A),
        "section_color": (0xB4, 0x86, 0x0B),
        "text_color": (0x3F, 0x3F, 0x46),
        "line_color": "D4AF37",
    },
    "sidebar": {
        "name_color": (0x11, 0x18, 0x27),
        "section_color": (0x0D, 0x94, 0x88),
        "text_color": (0x37, 0x41, 0x51),
        "line_color": "E5E7EB",
        "sidebar_fill": "EEF2F5",
    },
    # ---- M47 版式级新模板 ----
    "timeline": {
        "name_color": (0x11, 0x18, 0x27),
        "section_color": (0x0D, 0x94, 0x88),
        "text_color": (0x37, 0x41, 0x51),
        "line_color": "E5E7EB",
        "time_color": (0x94, 0xA3, 0xB8),
    },
    "banner": {
        "name_color": (0xFF, 0xFF, 0xFF),   # 页眉色块内白字
        "section_color": (0x1E, 0x3A, 0x8A),
        "text_color": (0x1F, 0x29, 0x37),
        "line_color": "1E3A8A",
        "banner_fill": "1E3A8A",            # 顶部整行深蓝底
        "banner_text": (0xFF, 0xFF, 0xFF),
    },
    "numbered": {
        "name_color": (0x0F, 0x17, 0x2A),
        "section_color": (0xB4, 0x53, 0x09),  # 焦糖橙编号
        "text_color": (0x37, 0x41, 0x51),
        "line_color": "FED7AA",
    },
    "sectionbar": {
        "name_color": (0x14, 0x2A, 0x1E),
        "section_color": (0x16, 0x65, 0x34),  # 墨绿
        "text_color": (0x33, 0x41, 0x55),
        "line_color": "E7F0E9",
        "bar_fill": "EAF3EC",                 # 区块标题通栏浅绿底纹
    },
}

# 前端模板选择器目录
TEMPLATE_CATALOG = [
    {"id": "classic", "name": "经典居中", "desc": "稳重通用，适合绝大多数岗位"},
    {"id": "sidebar", "name": "侧栏双栏", "desc": "左侧信息栏+右侧正文，分区清晰，推荐配照片"},
    {"id": "business", "name": "商务蓝", "desc": "深蓝分割线，国企/外企风格"},
    {"id": "elegant", "name": "典雅衬线", "desc": "宋体+金色点缀，庄重雅致"},
    {"id": "modern", "name": "现代竖标", "desc": "青绿竖线标题，简洁有活力"},
    {"id": "minimal", "name": "极简黑白", "desc": "黑白灰配色，适合技术/设计岗"},
    {"id": "academic", "name": "学术衬线", "desc": "Times 风格，适合高校/科研"},
    {"id": "creative", "name": "活力橙", "desc": "暖色调圆点标题，适合运营/市场"},
    {"id": "twocol", "name": "单行页眉", "desc": "姓名与联系方式同行，节省纵向空间"},
    {"id": "compact", "name": "紧凑单页", "desc": "行距压缩，内容多时一页放下"},
    {"id": "timeline", "name": "时间轴", "desc": "左时间右内容两列对齐，最贴近主流简历版式，推荐"},
    {"id": "banner", "name": "深色页眉", "desc": "顶部整行深蓝色块白字，互联网/设计岗常见风格"},
    {"id": "numbered", "name": "编号区块", "desc": "01/02/03 焦糖橙编号标题，层次分明个性鲜明"},
    {"id": "sectionbar", "name": "底纹标题", "desc": "区块标题通栏浅绿底纹，沉稳清晰，通用性强"},
]


def list_templates() -> list[dict]:
    return [dict(t) for t in TEMPLATE_CATALOG]


# ---------- 基础工具 ----------


def _set_cjk(run, east: str) -> None:
    """中文字体需要单独设置 eastAsia，否则 Word 里中文回落到默认字体"""
    rPr = run._element.get_or_add_rPr()
    rFonts = rPr.find(qn("w:rFonts"))
    if rFonts is None:
        rFonts = OxmlElement("w:rFonts")
        rPr.append(rFonts)
    rFonts.set(qn("w:eastAsia"), east)


def _add_bottom_border(paragraph, color="E5E7EB", size=6):
    pPr = paragraph._p.get_or_add_pPr()
    pBdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(size))
    bottom.set(qn("w:space"), "4")
    bottom.set(qn("w:color"), color)
    pBdr.append(bottom)
    pPr.append(pBdr)


def _shade_cell(cell, fill: str) -> None:
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:fill"), fill)
    tcPr.append(shd)


def _style_run(run, colors, size=10.5, bold=False, serif_east=None):
    run.font.size = Pt(size)
    run.font.bold = bold
    run.font.color.rgb = RGBColor(*colors["text_color"])
    if serif_east:
        _set_cjk(run, serif_east)
    return run


def _contacts(data) -> list[str]:
    """联系方式行：优先 contacts 列表；兼容旧版单字符串 contact（按分隔符拆分）"""
    items = [str(s).strip() for s in (data.get("contacts") or []) if str(s).strip()]
    if not items and data.get("contact"):
        items = [
            p.strip()
            for p in re.split(r"[|｜;/\n]", str(data["contact"]))
            if p.strip()
        ]
    intention = str(data.get("job_intention") or "").strip()
    if intention and not any("求职意向" in s for s in items):
        items.append(f"求职意向：{intention}")
    return items


def _add_photo(paragraph, photo_path, width_cm: float = 2.6):
    run = paragraph.add_run()
    run.add_picture(str(photo_path), width=Cm(width_cm))
    paragraph.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    return paragraph


def _name_run(p, data, colors, size: float, serif_east: str | None = None):
    r = p.add_run(data.get("name") or "个人简历")
    r.bold = True
    r.font.size = Pt(size)
    r.font.color.rgb = RGBColor(*colors["name_color"])
    if serif_east:
        _set_cjk(r, serif_east)
    return r


# ---------- 页眉（姓名 + 联系方式 + 可选照片） ----------
# 三种版式：center 居中式 / left 左对齐式 / inline 同行式


def _header(doc, data, colors, photo_path, mode: str, name_size: float,
            serif_east: str | None = None, contact_color=(0x88, 0x88, 0x88),
            contact_size: float = 10):
    contacts = _contacts(data)

    if photo_path is None:
        p = doc.add_paragraph()
        if mode == "center":
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            _name_run(p, data, colors, name_size, serif_east)
            if contacts:
                p2 = doc.add_paragraph()
                p2.alignment = WD_ALIGN_PARAGRAPH.CENTER
                _style_run(
                    p2.add_run("  |  ".join(contacts)), colors,
                    size=contact_size - 1,
                ).font.color.rgb = RGBColor(*contact_color)
        elif mode == "inline":
            _name_run(p, data, colors, name_size, serif_east)
            if contacts:
                r = p.add_run("    " + "  ".join(contacts))
                r.font.size = Pt(contact_size - 1)
                r.font.color.rgb = RGBColor(*contact_color)
        else:  # left
            _name_run(p, data, colors, name_size, serif_east)
            if contacts:
                p2 = doc.add_paragraph()
                _style_run(p2.add_run("  |  ".join(contacts)), colors,
                           size=contact_size - 1).font.color.rgb = RGBColor(*contact_color)
        return

    # 带照片：两列表格（左：姓名+联系方式；右：一寸照，右上角符合中文简历惯例）
    table = doc.add_table(rows=1, cols=2)
    table.autofit = False
    left, right = table.rows[0].cells
    left.width = Cm(12.8)
    right.width = Cm(3.4)
    right.vertical_alignment = WD_ALIGN_VERTICAL.CENTER

    lp = left.paragraphs[0]
    if mode == "center":
        lp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _name_run(lp, data, colors, name_size, serif_east)
    if contacts:
        cp = left.add_paragraph()
        if mode == "center":
            cp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        r = cp.add_run("  |  ".join(contacts))
        r.font.size = Pt(contact_size - 1)
        r.font.color.rgb = RGBColor(*contact_color)
        if serif_east:
            _set_cjk(r, serif_east)

    _add_photo(right.paragraphs[0], photo_path)


# ---------- 正文区块渲染器 ----------


def _render_body(doc, data, colors, *, titles=None, title_marker="", title_upper=False,
                 title_size=13, title_border=True, bullet=True, left_indent=0.0,
                 line_space=2, body_size=10.5, serif_east=None, skip=(),
                 skill_sep=" · "):
    """统一渲染 简介/教育/工作/项目 + 技能 + 证书。

    titles: {"summary": "关于我", ...} 自定义标题文案
    """
    titles = titles or {}
    plan = [
        ("summary", titles.get("summary", "个人简介"), [data.get("summary", "")]),
        ("education", titles.get("education", "教育经历"), data.get("education", [])),
        ("experience", titles.get("experience", "工作经历"), data.get("experience", [])),
        ("projects", titles.get("projects", "项目经历"), data.get("projects", [])),
    ]
    for key, title, lines in plan:
        lines = [str(x).strip() for x in (lines or []) if str(x).strip()]
        if key in skip or not lines:
            continue
        _section_title(doc, title, colors, marker=title_marker, upper=title_upper,
                       size=title_size, border=title_border, serif_east=serif_east)
        for line in lines:
            if bullet:
                _add_bullet(doc, line, colors, size=body_size, indent=left_indent,
                            serif_east=serif_east)
            else:
                p = doc.add_paragraph(line)
                p.paragraph_format.space_after = Pt(line_space)
                if left_indent:
                    p.paragraph_format.left_indent = Cm(left_indent)
                _style_run(p.runs[0] if p.runs else p.add_run(line), colors,
                           size=body_size, serif_east=serif_east)
        doc.add_paragraph()

    skills = data.get("skills") or []
    if skills:
        _section_title(doc, titles.get("skills", "技能"), colors, marker=title_marker,
                       upper=title_upper, size=title_size, border=title_border,
                       serif_east=serif_east)
        p = doc.add_paragraph(skill_sep.join(skills))
        p.paragraph_format.space_after = Pt(line_space)
        if left_indent:
            p.paragraph_format.left_indent = Cm(left_indent)
        _style_run(p.runs[0], colors, size=body_size, serif_east=serif_east)

    certs = data.get("certificates") or []
    if certs:
        _section_title(doc, titles.get("certificates", "证书"), colors,
                       marker=title_marker, upper=title_upper, size=title_size,
                       border=title_border, serif_east=serif_east)
        for c in certs:
            if bullet:
                _add_bullet(doc, str(c), colors, size=body_size, indent=left_indent,
                            serif_east=serif_east)
            else:
                p = doc.add_paragraph(str(c))
                p.paragraph_format.space_after = Pt(line_space)
                _style_run(p.runs[0], colors, size=body_size, serif_east=serif_east)


def _section_title(doc, title, colors, marker="", upper=False, size=13, border=True,
                   serif_east=None):
    p = doc.add_paragraph()
    if marker:
        r = p.add_run(marker)
        r.font.size = Pt(size + 1)
        r.font.color.rgb = RGBColor(*colors["section_color"])
    r = p.add_run(title.upper() if upper else title)
    r.bold = True
    r.font.size = Pt(size)
    r.font.color.rgb = RGBColor(*colors["section_color"])
    if serif_east:
        _set_cjk(r, serif_east)
    if border:
        _add_bottom_border(p, colors["line_color"])
    return p


def _add_bullet(doc, line, colors, size=10.5, indent=0.0, serif_east=None):
    p = doc.add_paragraph(line, style="List Bullet")
    p.paragraph_format.space_after = Pt(2)
    if indent:
        p.paragraph_format.left_indent = Cm(indent)
    for r in p.runs:
        r.font.size = Pt(size)
        r.font.color.rgb = RGBColor(*colors["text_color"])
        if serif_east:
            _set_cjk(r, serif_east)
    return p


# ---------- 各模板 ----------


def _build_classic(doc, data, photo_path=None):
    colors = TEMPLATES["classic"]
    _header(doc, data, colors, photo_path, "center", 22)
    doc.add_paragraph()
    _render_body(doc, data, colors, bullet=True)


def _build_modern(doc, data, photo_path=None):
    colors = TEMPLATES["modern"]
    _header(doc, data, colors, photo_path, "left", 26)
    p = doc.add_paragraph()
    _add_bottom_border(p, colors["line_color"], size=14)
    doc.add_paragraph()
    _render_body(doc, data, colors, title_marker="▍ ", title_border=False,
                 bullet=False, left_indent=0.5, skill_sep=" / ")


def _build_minimal(doc, data, photo_path=None):
    colors = TEMPLATES["minimal"]
    _header(doc, data, colors, photo_path, "center", 20, contact_color=(0x99, 0x99, 0x99),
            contact_size=9)
    doc.add_paragraph()
    _render_body(doc, data, colors, title_size=11, title_border=False, bullet=False)


def _build_business(doc, data, photo_path=None):
    colors = TEMPLATES["business"]
    _header(doc, data, colors, photo_path, "left", 24, contact_color=(0x66, 0x66, 0x66))
    p = doc.add_paragraph()
    _add_bottom_border(p, colors["line_color"], size=12)
    doc.add_paragraph()
    _render_body(doc, data, colors, title_upper=True, title_size=12, bullet=True,
                 skill_sep=" | ")


def _build_academic(doc, data, photo_path=None):
    colors = TEMPLATES["academic"]
    _header(doc, data, colors, photo_path, "center", 20, contact_color=(0x66, 0x66, 0x66),
            serif_east="宋体")
    doc.add_paragraph()
    _render_body(doc, data, colors, title_size=13, bullet=False, body_size=11,
                 serif_east="宋体", skill_sep=" · ")


def _build_creative(doc, data, photo_path=None):
    colors = TEMPLATES["creative"]
    _header(doc, data, colors, photo_path, "left", 28)
    doc.add_paragraph()
    _render_body(
        doc, data, colors,
        titles={"summary": "关于我", "education": "教育", "experience": "经历",
                "projects": "项目", "skills": "技能", "certificates": "证书"},
        title_marker="● ", title_size=14, title_border=False, bullet=False,
        left_indent=0.6, skill_sep=" · ",
    )


def _build_twocol(doc, data, photo_path=None):
    colors = TEMPLATES["twocol"]
    _header(doc, data, colors, photo_path, "inline", 22)
    p = doc.add_paragraph()
    _add_bottom_border(p, colors["line_color"])
    doc.add_paragraph()
    _render_body(doc, data, colors, title_size=12, bullet=True, skill_sep=" · ")


def _build_compact(doc, data, photo_path=None):
    colors = TEMPLATES["compact"]
    _header(doc, data, colors, photo_path, "center", 18, contact_size=9)
    doc.add_paragraph()
    _render_body(
        doc, data, colors,
        titles={"summary": "简介", "education": "教育", "experience": "工作",
                "projects": "项目"},
        title_marker="— ", title_size=11, title_border=False, bullet=False,
        line_space=1, body_size=10, skill_sep=" · ",
    )


def _build_elegant(doc, data, photo_path=None):
    """典雅衬线：宋体正文 + 金色区块标题"""
    colors = TEMPLATES["elegant"]
    _header(doc, data, colors, photo_path, "center", 21, serif_east="宋体",
            contact_color=(0x8A, 0x6D, 0x3B))
    doc.add_paragraph()
    _render_body(doc, data, colors, title_size=12.5, bullet=True, serif_east="宋体")


def _build_sidebar(doc, data, photo_path=None):
    """侧栏双栏：左侧浅色信息栏（照片/联系方式/技能/证书），右侧正文"""
    colors = TEMPLATES["sidebar"]
    table = doc.add_table(rows=1, cols=2)
    table.autofit = False
    side, main = table.rows[0].cells
    side.width = Cm(5.6)
    main.width = Cm(10.8)
    _shade_cell(side, colors["sidebar_fill"])
    side.vertical_alignment = WD_ALIGN_VERTICAL.TOP

    # 左栏：照片 + 联系方式 + 技能 + 证书
    if photo_path is not None:
        pp = side.add_paragraph()
        pp.alignment = WD_ALIGN_PARAGRAPH.CENTER
        pp.add_run().add_picture(str(photo_path), width=Cm(2.8))
        side.add_paragraph()

    def side_title(text):
        p = side.add_paragraph()
        r = p.add_run(text)
        r.bold = True
        r.font.size = Pt(12)
        r.font.color.rgb = RGBColor(*colors["section_color"])
        _add_bottom_border(p, colors["line_color"], size=4)
        return p

    contacts = _contacts(data)
    if contacts:
        side_title("联系方式")
        for c in contacts:
            p = side.add_paragraph(str(c))
            p.paragraph_format.space_after = Pt(2)
            for r in p.runs:
                r.font.size = Pt(9.5)
                r.font.color.rgb = RGBColor(*colors["text_color"])
        side.add_paragraph()

    if data.get("skills"):
        side_title("技能")
        for s in data["skills"]:
            p = side.add_paragraph("· " + str(s))
            p.paragraph_format.space_after = Pt(1)
            for r in p.runs:
                r.font.size = Pt(9.5)
                r.font.color.rgb = RGBColor(*colors["text_color"])
        side.add_paragraph()

    if data.get("certificates"):
        side_title("证书")
        for c in data["certificates"]:
            p = side.add_paragraph("· " + str(c))
            p.paragraph_format.space_after = Pt(1)
            for r in p.runs:
                r.font.size = Pt(9.5)
                r.font.color.rgb = RGBColor(*colors["text_color"])

    # 右栏：姓名 + 正文
    name_p = main.paragraphs[0]
    _name_run(name_p, data, colors, 26)
    intention = str(data.get("job_intention") or "").strip()
    if intention:
        p = main.add_paragraph(intention)
        for r in p.runs:
            r.font.size = Pt(11)
            r.font.color.rgb = RGBColor(*colors["section_color"])
        _add_bottom_border(p, colors["line_color"], size=10)
    main.add_paragraph()

    _render_body(doc, data, colors, title_marker="▍ ", title_border=False,
                 bullet=True, skip=("skills", "certificates"))


# ---------- M47 版式级新模板 ----------

_TIME_HINT_WORDS = ("至今", "现在", "present", "在读", "目前")

def _split_time_head(line: str):
    """把 '2020-2024 某公司 后端' 拆为 (时间, 其余)；非时间开头返回 (None, 原行)。

    条目字符串是 time/公司/职位空格拼接的（EditorView buildWordData），首 token
    含年份数字或时间提示词即视为时间。
    """
    parts = line.split(None, 1)
    if not parts:
        return None, line
    head = parts[0].lower()
    if any(ch.isdigit() for ch in head) or any(w in head for w in _TIME_HINT_WORDS):
        return parts[0], parts[1] if len(parts) > 1 else ""
    return None, line


def _group_entries(lines):
    """扁平行列表 → 条目组：首行开条目（拆时间），后续行归入该条目 desc。"""
    entries = []
    for line in lines:
        line = str(line).strip()
        if not line:
            continue
        if entries and len(line) > 24 and not any(ch.isdigit() for ch in line[:4]):
            # 启发式：后续长描述行（行首非年份）归入当前条目
            entries[-1]["desc"].append(line)
            continue
        time, rest = _split_time_head(line)
        entries.append({"time": time or "", "head": rest or line, "desc": []})
    return entries


def _timeline_section(doc, entries, colors, *, head_size=11, desc_size=10):
    """时间轴区块：每条目一行两列表格（左时间灰字右对齐，右标题加粗+描述）。"""
    for e in entries:
        table = doc.add_table(rows=1, cols=2)
        table.autofit = False
        left, right = table.rows[0].cells
        left.width = Cm(3.4)
        right.width = Cm(12.4)
        lp = left.paragraphs[0]
        lp.alignment = WD_ALIGN_PARAGRAPH.RIGHT
        if e["time"]:
            r = lp.add_run(e["time"])
            r.font.size = Pt(desc_size)
            r.font.color.rgb = RGBColor(*colors.get("time_color", (0x94, 0xA3, 0xB8)))
        rp = right.paragraphs[0]
        r = rp.add_run(e["head"])
        r.bold = True
        r.font.size = Pt(head_size)
        r.font.color.rgb = RGBColor(*colors["text_color"])
        for d in e["desc"]:
            dp = right.add_paragraph(d)
            dp.paragraph_format.space_after = Pt(1)
            for run in dp.runs:
                run.font.size = Pt(desc_size)
                run.font.color.rgb = RGBColor(*colors["text_color"])
    doc.add_paragraph()


def _entries_of(data, key):
    return _group_entries(data.get(key) or [])


def _build_timeline(doc, data, photo_path=None):
    """时间轴：左时间右内容两列对齐，最贴近主流真实简历版式"""
    colors = TEMPLATES["timeline"]
    _header(doc, data, colors, photo_path, "left", 22)
    p = doc.add_paragraph()
    _add_bottom_border(p, colors["line_color"], size=12)
    doc.add_paragraph()

    sections = [
        ("education", "教育经历", _entries_of(data, "education")),
        ("experience", "工作经历", _entries_of(data, "experience")),
        ("projects", "项目经历", _entries_of(data, "projects")),
    ]
    for _, title, entries in sections:
        if not entries:
            continue
        _section_title(doc, title, colors, size=12.5)
        _timeline_section(doc, entries, colors)

    skills = data.get("skills") or []
    if skills:
        _section_title(doc, "技能", colors, size=12.5)
        p = doc.add_paragraph(" · ".join(skills))
        p.paragraph_format.space_after = Pt(2)
        _style_run(p.runs[0], colors)
        doc.add_paragraph()
    certs = data.get("certificates") or []
    if certs:
        _section_title(doc, "证书", colors, size=12.5)
        for c in certs:
            _add_bullet(doc, str(c), colors)
        doc.add_paragraph()
    summary = str(data.get("summary") or "").strip()
    if summary:
        _section_title(doc, "个人简介", colors, size=12.5)
        p = doc.add_paragraph(summary)
        p.paragraph_format.space_after = Pt(2)
        _style_run(p.runs[0] if p.runs else p.add_run(summary), colors)


def _build_banner(doc, data, photo_path=None):
    """深色页眉：顶部整行深蓝色块（白字姓名+联系方式），互联网风格"""
    colors = TEMPLATES["banner"]
    table = doc.add_table(rows=1, cols=2)
    table.autofit = False
    left, right = table.rows[0].cells
    left.width = Cm(12.8)
    right.width = Cm(3.4)
    _shade_cell(left, colors["banner_fill"])
    _shade_cell(right, colors["banner_fill"])
    lp = left.paragraphs[0]
    r = lp.add_run(data.get("name") or "个人简历")
    r.bold = True
    r.font.size = Pt(24)
    r.font.color.rgb = RGBColor(*colors["banner_text"])
    contacts = _contacts(data)
    if contacts:
        cp = left.add_paragraph("  |  ".join(contacts))
        for run in cp.runs:
            run.font.size = Pt(9.5)
            run.font.color.rgb = RGBColor(0xD9, 0xE2, 0xF5)
    if photo_path is not None:
        pp = right.paragraphs[0]
        run = pp.add_run()
        run.add_picture(str(photo_path), width=Cm(2.4))
        pp.alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph()

    _render_body(
        doc, data, colors,
        titles={"summary": "关于我"},
        title_marker="— ", title_size=12, title_border=True, bullet=True,
        skill_sep=" / ",
    )


def _build_numbered(doc, data, photo_path=None):
    """编号区块：01/02/03 焦糖橙编号 + 区块标题，层次个性"""
    colors = TEMPLATES["numbered"]
    _header(doc, data, colors, photo_path, "left", 26, contact_color=(0x9A, 0x6B, 0x3F))
    doc.add_paragraph()

    # 求职意向高亮条（浅橙底）
    intention = str(data.get("job_intention") or "").strip()
    if intention:
        t = doc.add_table(rows=1, cols=1)
        t.autofit = False
        cell = t.rows[0].cells[0]
        cell.width = Cm(15.8)
        _shade_cell(cell, "FEF3E8")
        ip = cell.paragraphs[0]
        r = ip.add_run(f"求职意向：{intention}")
        r.bold = True
        r.font.size = Pt(11.5)
        r.font.color.rgb = RGBColor(*colors["section_color"])
        doc.add_paragraph()

    idx = 1
    plan = [
        ("summary", "个人简介", [data.get("summary", "")]),
        ("education", "教育经历", data.get("education", [])),
        ("experience", "工作经历", data.get("experience", [])),
        ("projects", "项目经历", data.get("projects", [])),
    ]
    for _, title, lines in plan:
        lines = [str(x).strip() for x in (lines or []) if str(x).strip()]
        if not lines:
            continue
        p = doc.add_paragraph()
        r = p.add_run(f"{idx:02d} ")
        r.bold = True
        r.font.size = Pt(14)
        r.font.color.rgb = RGBColor(*colors["section_color"])
        r2 = p.add_run(title)
        r2.bold = True
        r2.font.size = Pt(13)
        r2.font.color.rgb = RGBColor(*colors["name_color"])
        _add_bottom_border(p, colors["line_color"], size=8)
        for line in lines:
            _add_bullet(doc, line, colors, size=10.5)
        doc.add_paragraph()
        idx += 1

    skills = data.get("skills") or []
    if skills:
        p = doc.add_paragraph()
        r = p.add_run(f"{idx:02d} ")
        r.bold = True
        r.font.size = Pt(14)
        r.font.color.rgb = RGBColor(*colors["section_color"])
        r2 = p.add_run("技能")
        r2.bold = True
        r2.font.size = Pt(13)
        r2.font.color.rgb = RGBColor(*colors["name_color"])
        _add_bottom_border(p, colors["line_color"], size=8)
        sp = doc.add_paragraph(" · ".join(skills))
        sp.paragraph_format.space_after = Pt(2)
        _style_run(sp.runs[0], colors)
        idx += 1
    certs = data.get("certificates") or []
    if certs:
        for c in certs:
            _add_bullet(doc, str(c), colors)


def _build_sectionbar(doc, data, photo_path=None):
    """底纹标题：区块标题通栏浅绿底纹条，沉稳通用"""
    colors = TEMPLATES["sectionbar"]

    def bar_title(text):
        t = doc.add_table(rows=1, cols=1)
        t.autofit = False
        cell = t.rows[0].cells[0]
        cell.width = Cm(15.8)
        _shade_cell(cell, colors["bar_fill"])
        bp = cell.paragraphs[0]
        r = bp.add_run("  " + text)
        r.bold = True
        r.font.size = Pt(12)
        r.font.color.rgb = RGBColor(*colors["section_color"])

    # 照片复用左页眉表格（姓名+联系方式+右侧照片）
    _header(doc, data, colors, photo_path, "left", 22)
    doc.add_paragraph()

    summary = str(data.get("summary") or "").strip()
    if summary:
        bar_title("个人简介")
        p = doc.add_paragraph(summary)
        p.paragraph_format.space_after = Pt(2)
        _style_run(p.runs[0] if p.runs else p.add_run(summary), colors)
        doc.add_paragraph()
    for key, title in (("education", "教育经历"), ("experience", "工作经历"), ("projects", "项目经历")):
        lines = [str(x).strip() for x in (data.get(key) or []) if str(x).strip()]
        if not lines:
            continue
        bar_title(title)
        for line in lines:
            _add_bullet(doc, line, colors)
        doc.add_paragraph()
    skills = data.get("skills") or []
    if skills:
        bar_title("技能")
        sp = doc.add_paragraph(" · ".join(skills))
        sp.paragraph_format.space_after = Pt(2)
        _style_run(sp.runs[0], colors)
        doc.add_paragraph()
    certs = data.get("certificates") or []
    if certs:
        bar_title("证书")
        for c in certs:
            _add_bullet(doc, str(c), colors)


BUILDERS = {
    "classic": _build_classic,
    "modern": _build_modern,
    "minimal": _build_minimal,
    "business": _build_business,
    "academic": _build_academic,
    "creative": _build_creative,
    "twocol": _build_twocol,
    "compact": _build_compact,
    "elegant": _build_elegant,
    "sidebar": _build_sidebar,
    "timeline": _build_timeline,
    "banner": _build_banner,
    "numbered": _build_numbered,
    "sectionbar": _build_sectionbar,
}


def generate_resume_docx(data: dict, template: str = "classic", photo_path=None) -> bytes:
    """生成 Word 简历。

    data 键：name / contacts(list) 或 contact(str) / job_intention / summary /
    education / experience / projects / skills / certificates
    photo_path: 证件照文件路径（JPG/PNG），None 则不嵌入
    """
    doc = Document()
    for section in doc.sections:
        section.top_margin = Cm(1.6)
        section.bottom_margin = Cm(1.6)
        section.left_margin = Cm(2.0)
        section.right_margin = Cm(2.0)

    builder = BUILDERS.get(template, _build_classic)
    builder(doc, data, photo_path)

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
