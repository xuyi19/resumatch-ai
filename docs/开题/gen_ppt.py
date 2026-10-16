# -*- coding: utf-8 -*-
"""基于河北东方学院 PPT 模板生成开题答辩 PPT（10 页）。

模板顶部红带（含校徽校名）高约 0.95in，内容区从 1.75in 起。
"""
from pptx import Presentation
from pptx.util import Inches, Pt, Emu
from pptx.dml.color import RGBColor
from pptx.enum.text import PP_ALIGN, MSO_ANCHOR
from pptx.oxml.ns import qn

TPL = r"c:\Users\许\.trae-cn\attachments\82c0a6b1-59f7-4296-a7e6-6b7a7173adb1_c2be1c26-2087-4480-b608-280d61a9c964_河北东方学院-PPT模版.pptx"
OUT = r"e:\code\resumatch-ai\docs\开题\开题答辩PPT.pptx"
IMG = r"e:\code\resumatch-ai\docs\images"

RED = RGBColor(0xC0, 0x00, 0x00)
DARK = RGBColor(0x33, 0x33, 0x33)
GRAY = RGBColor(0x59, 0x59, 0x59)

TITLE = "基于大模型的智能简历诊断与岗位匹配推荐系统的设计与实现"


def set_ea(run, name="微软雅黑"):
    rPr = run._r.get_or_add_rPr()
    ea = rPr.find(qn("a:ea"))
    if ea is None:
        ea = rPr.makeelement(qn("a:ea"), {})
        rPr.append(ea)
    ea.set("typeface", name)


prs = Presentation(TPL)
blank = None
for layout in prs.slide_masters[0].slide_layouts:
    if layout.name == "空白":
        blank = layout
        break
if blank is None:
    blank = prs.slide_masters[0].slide_layouts[-1]


def add_text(slide, l, t, w, h, lines, align=PP_ALIGN.LEFT, anchor=MSO_ANCHOR.TOP):
    """lines: [(text, size, bold, color, space_after)]"""
    box = slide.shapes.add_textbox(Emu(int(l)), Emu(int(t)), Emu(int(w)), Emu(int(h)))
    tf = box.text_frame
    tf.word_wrap = True
    tf.vertical_anchor = anchor
    for i, (text, size, bold, color, after) in enumerate(lines):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.alignment = align
        p.space_after = Pt(after)
        r = p.add_run()
        r.text = text
        r.font.size = Pt(size)
        r.font.bold = bold
        r.font.color.rgb = color
        r.font.name = "微软雅黑"
        set_ea(r)
    return box


def new_page(title=None):
    s = prs.slides.add_slide(blank)
    if title:
        add_text(s, Inches(0.55), Inches(1.02), Inches(9), Inches(0.62),
                 [(title, 24, True, RED, 0)])
        line = s.shapes.add_shape(1, Inches(0.58), Inches(1.62), Inches(8.84), Pt(2))
        line.fill.solid()
        line.fill.fore_color.rgb = RED
        line.line.fill.background()
    return s


def bullets(slide, items, t=Inches(1.9), w=Inches(8.6), h=Inches(3.5), size=14):
    box = slide.shapes.add_textbox(Inches(0.7), t, w, h)
    tf = box.text_frame
    tf.word_wrap = True
    for i, (text, lvl) in enumerate(items):
        p = tf.paragraphs[0] if i == 0 else tf.add_paragraph()
        p.space_after = Pt(6 if lvl == 0 else 4)
        if lvl:
            p.level = 1
        r = p.add_run()
        r.text = ("● " + text) if lvl == 0 else ("— " + text)
        r.font.size = Pt(size if lvl == 0 else size - 1.5)
        r.font.color.rgb = DARK if lvl == 0 else GRAY
        r.font.name = "微软雅黑"
        set_ea(r)
    return box


# ---------- 第1页：封面 ----------
cover = prs.slides[0]
add_text(cover, Inches(0.8), Inches(2.0), Inches(8.4), Inches(1.9), [
    ("毕业设计（论文）开题答辩", 20, False, GRAY, 10),
    (TITLE, 30, True, RED, 0),
], align=PP_ALIGN.CENTER, anchor=MSO_ANCHOR.MIDDLE)
add_text(cover, Inches(0.8), Inches(4.35), Inches(8.4), Inches(1.4), [
    ("答辩人：（姓名）    学号：（学号）", 16, False, DARK, 6),
    ("学院：（学院）    专业：（专业）", 16, False, DARK, 6),
    ("指导教师：（教师姓名）    2026 年 10 月", 16, False, DARK, 0),
], align=PP_ALIGN.CENTER)

# ---------- 第2页：目录 ----------
s = new_page("目 录")
bullets(s, [
    ("一、研究背景及意义", 0),
    ("二、国内外研究现状", 0),
    ("三、研究内容与技术路线", 0),
    ("四、系统原型展示", 0),
    ("五、进度安排", 0),
    ("六、参考文献", 0),
], t=Inches(2.0), size=18)

# ---------- 第3页：背景与意义 ----------
s = new_page("一、研究背景及意义")
bullets(s, [
    ("就业形势：2025 届全国高校毕业生达 1222 万人，校招竞争持续加剧", 0),
    ("痛点一：人岗信息不对称，凭感觉海投，反馈率低、求职周期长", 0),
    ("痛点二：现有简历工具只做格式美化与通用打分，无法结合具体岗位给出可用的改写结果", 0),
    ("技术机遇：大语言模型能力趋实用，但单提示词点评存在结论发散、无中间过程、证据不可溯三大缺陷", 0),
    ("研究意义：实践上把模型能力转化为「差在哪、如何改」的可解释求职服务；技术上探索多智能体编排 + RAG 证据接地的垂直落地范式", 0),
], t=Inches(1.9), size=14.5)

# ---------- 第4页：现状 ----------
s = new_page("二、国内外研究现状")
add_text(s, Inches(0.7), Inches(1.82), Inches(8.6), Inches(0.4), [("国外", 16, True, RED, 0)])
bullets(s, [
    ("基础模型：Transformer → GPT-3 少样本学习 → GPT-4 实用化；RAG 范式提升事实性与可溯源性", 0),
    ("编排框架：LangChain / LangGraph 提供状态图、中断恢复等原语", 0),
    ("产品：Simplify Copilot 半自动投递只解决「投」环节；AIHawk 全自动投递受平台风控限制", 0),
], t=Inches(2.22), h=Inches(1.55), size=13.5)
add_text(s, Inches(0.7), Inches(3.85), Inches(8.6), Inches(0.4), [("国内", 16, True, RED, 0)])
bullets(s, [
    ("平台内建 AI 简历功能点状有限；通用大模型问答点评输出发散、无证据", 0),
    ("传统简历工具以格式检查为主；多智能体框架兴起，但用于简历诊断且证据可溯的公开研究仍较少", 0),
], t=Inches(4.25), h=Inches(1.1), size=13.5)

# ---------- 第5页：研究内容 ----------
s = new_page("三、研究内容（五项）")
bullets(s, [
    ("1. 智能简历诊断工作流：LangGraph 状态图编排解析 / 岗位分析 / 评分 / 差距 / 改写智能体，并行解析 + interrupt 动态追问", 0),
    ("2. 任务内证据接地（核心创新）：简历与 JD 切块建临时索引，结论全部回链原文；四层防幻觉体系", 0),
    ("3. 岗位匹配推荐：多来源岗位聚合，「关键词粗筛 + 大模型语义精排」两阶段策略，输出匹配分与推荐理由", 0),
    ("4. 流式交互与结构化输出：SSE 实时推送；Schema 注入 + 括号平衡提取 + 纠错重试三层容错", 0),
    ("5. 系统实现与评估：FastAPI + Vue3；桌面 exe + 网站双形态；消融 / 稳定性 / 压测三维评估", 0),
], t=Inches(1.95), size=13.5)

# ---------- 第6页：技术路线 ----------
s = new_page("三、技术路线（分层架构）")
bullets(s, [
    ("交互层：Vue3 网页界面 + 桌面客户端（免安装）", 0),
    ("服务层：FastAPI 接口 + SSE 实时推送", 0),
    ("编排层：LangGraph 多智能体诊断链（并行解析 / 条件分支 / 动态追问）", 0),
    ("能力层：兼容大模型 + 任务内 RAG 证据库 + 四层校验；「粗筛 + 精排」两阶段岗位匹配推荐", 0),
    ("数据层：SQLite 存储简历、岗位库、诊断记录与会话", 0),
    ("研究方法：文献研究法 + 原型系统法 + 实验验证法", 0),
], t=Inches(1.95), size=15)

# ---------- 第7页：关键技术与难点 ----------
s = new_page("三、关键技术与难点")
bullets(s, [
    ("难点 1：大模型结构化输出不稳定、多厂商行为差异大", 0),
    ("对策：Schema 注入 + 括号平衡提取 + 纠错重试三层容错", 1),
    ("难点 2：诊断结论幻觉、证据不可溯", 0),
    ("对策：任务内 RAG 证据接地 + 四层防幻觉（注入 / 约束 / 校验 / 标注）", 1),
    ("难点 3：多智能体链路耗时长，用户体验差", 0),
    ("对策：解析阶段并行化 + SSE 全程流式反馈 + 断点续跑", 1),
    ("难点 4：岗位匹配的语义鸿沟与调用成本矛盾", 0),
    ("对策：「关键词粗筛 + 大模型精排」两阶段，先过滤后排序", 1),
], t=Inches(1.9), size=13.5)

# ---------- 第8页：预期成果与创新点 ----------
s = new_page("三、预期成果与创新点")
add_text(s, Inches(0.7), Inches(1.82), Inches(8.6), Inches(0.4), [("预期成果", 16, True, RED, 0)])
bullets(s, [
    ("可运行的完整系统：智能简历诊断 + 岗位匹配推荐（桌面 exe + 网站双形态）", 0),
    ("毕业设计（论文）一篇及配套实验数据", 0),
], t=Inches(2.22), h=Inches(1.1), size=13.5)
add_text(s, Inches(0.7), Inches(3.45), Inches(8.6), Inches(0.4), [("创新点", 16, True, RED, 0)])
bullets(s, [
    ("任务内证据接地：区别于外挂知识库式 RAG，结论全部回链本次简历原文", 0),
    ("模型自主判定追问：interrupt 人在回路，由信息缺口动态决定追问数量", 0),
    ("两阶段岗位匹配：粗筛与精排结合，兼顾调用成本与语义相关性", 0),
], t=Inches(3.85), h=Inches(1.5), size=13.5)

# ---------- 第9页：系统原型 ----------
s = new_page("四、系统原型展示")
s.shapes.add_picture(IMG + r"\result.png", Inches(0.55), Inches(1.95), width=Inches(4.35))
s.shapes.add_picture(IMG + r"\jobs.png", Inches(5.15), Inches(1.95), width=Inches(4.35))
add_text(s, Inches(0.55), Inches(4.75), Inches(4.35), Inches(0.4),
         [("智能简历诊断：六维评分 + 证据引用", 12, False, GRAY, 0)], align=PP_ALIGN.CENTER)
add_text(s, Inches(5.15), Inches(4.75), Inches(4.35), Inches(0.4),
         [("岗位匹配推荐：粗筛精排 + 岗位库管理", 12, False, GRAY, 0)], align=PP_ALIGN.CENTER)

# ---------- 第10页：进度安排 ----------
s = new_page("五、进度安排")
rows = [
    ("阶段", "时间", "工作内容"),
    ("一", "2026.10", "文献调研，完成开题报告与开题答辩"),
    ("二", "2026.11 - 12", "需求分析与总体设计（选型 / 数据库 / 诊断流程架构）"),
    ("三", "2026.12 - 2027.01", "核心模块开发（工作流 / 证据接地 / 流式），撰写初稿"),
    ("四", "2027.02 - 03", "功能完善与实验评估，参加中期检查"),
    ("五", "2027.04", "论文修改、查重与定稿"),
    ("六", "2027.05", "答辩准备，参加毕业答辩"),
]
tb = s.shapes.add_table(7, 3, Inches(0.7), Inches(1.95), Inches(8.6), Inches(3.35)).table
tb.columns[0].width = Inches(0.9)
tb.columns[1].width = Inches(2.2)
tb.columns[2].width = Inches(5.5)
for ri, row in enumerate(rows):
    for ci, txt in enumerate(row):
        cell = tb.cell(ri, ci)
        cell.text = ""
        p = cell.text_frame.paragraphs[0]
        r = p.add_run()
        r.text = txt
        r.font.size = Pt(12.5)
        r.font.bold = ri == 0
        r.font.color.rgb = RGBColor(0xFF, 0xFF, 0xFF) if ri == 0 else DARK
        r.font.name = "微软雅黑"
        set_ea(r)
        if ri == 0:
            cell.fill.solid()
            cell.fill.fore_color.rgb = RED

# ---------- 第11页：参考文献 ----------
s = new_page("六、参考文献")
refs = [
    "[1] 车万翔, 窦嘉玮, 闫崑, 等. 大模型时代的自然语言处理——挑战、机遇与发展. 中国科学: 信息科学, 2023.",
    "[2] 邱锡鹏. 神经网络与深度学习. 机械工业出版社, 2020.",
    "[3] 周志华. 机器学习. 清华大学出版社, 2016.",
    "[4] 李航. 统计学习方法（第 2 版）. 清华大学出版社, 2019.",
    "[5] 宗成庆. 统计自然语言处理（第 2 版）. 清华大学出版社, 2013.",
    "[6] 中国信息通信研究院. 人工智能发展报告（2024 年）, 2024.",
    "[7] 教育部. 2025 届全国普通高校毕业生规模预计达 1222 万人, 2024.",
    "[8] 中国互联网络信息中心. 第 53 次中国互联网络发展状况统计报告, 2024.",
]
bullets(s, [(r, 0) for r in refs], t=Inches(1.95), size=13.5)

# ---------- 第12页：致谢 ----------
s = new_page()
add_text(s, Inches(0.8), Inches(2.8), Inches(8.4), Inches(1.2), [
    ("恳请各位老师批评指正！", 32, True, RED, 0),
], align=PP_ALIGN.CENTER)

prs.save(OUT)
print("saved:", OUT)
