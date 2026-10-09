"""质量评估脚本（M6 基础 + M11-C 扩展）：简历-JD 标注集多次诊断，统计评分稳定性、
改写覆盖度与证据引用质量；支持消融对比（完整 / 无RAG / 无refine / 在线追问）。

用法（backend 目录下）：
    python scripts/evaluate.py                     # 稳定性：3 用例 × 2 次
    python scripts/evaluate.py --ablation          # 消融对比：4 变体 × 用例1
    python scripts/evaluate.py --ablation --case 2 # 指定消融用例
    python scripts/evaluate.py --baseline          # 基线对比：完整链路 vs 全文直塞（3 用例各 1 轮）
    python scripts/evaluate.py --api-key sk-xxx --model deepseek-chat

产出：docs/ 下独立评估报告（评分均值/标准差、改写覆盖度、证据引用覆盖/推断率、消融表、
      基线对比表）；历史结果已并入 docs/ResuMatch-AI-技术说明文档.md 第 13 章

说明：语义匹配采用轻量词面重叠指标（不引入 embedding/torch，
避免桌面版体积膨胀；LLM 链路本身即语义匹配主通道）。
"""
import argparse
import asyncio
import re
import statistics
import sys
import time
from contextlib import ExitStack
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from pydantic import BaseModel

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.config import settings  # noqa: E402
from app.services.diagnosis_service import DiagnosisService  # noqa: E402

# ---------------- 标注集：3 组简历-JD 样本 ----------------
# expected.match: high / medium / low —— 期望 LLM 给出的相对匹配水平（报告人工核对用）
CASES = [
    {
        "name": "后端岗高匹配",
        "expected": "high",
        "resume": (
            "张伟 ｜ 本科 · 计算机科学 ｜ 5 年后端开发\n"
            "技能：Python、FastAPI、MySQL、Redis、Docker、Nginx\n"
            "经历：某电商公司 高级后端工程师（2021-2026）\n"
            "- 主导订单系统重构，QPS 从 800 提升至 3500，接口 P99 延迟降低 60%\n"
            "- 设计库存扣减方案，超卖率由 0.5% 降至 0，支撑双 11 峰值 12 万单/小时\n"
            "- 搭建 CI/CD 流水线，发布耗时从 40 分钟缩短至 8 分钟\n"
            "项目：分布式支付网关——日均处理 300 万笔交易，可用性 99.99%"
        ),
        "jd": (
            "岗位：高级 Python 后端工程师\n"
            "要求：3 年以上 Python 开发经验；熟练掌握 FastAPI/Flask 框架；\n"
            "熟悉 MySQL 索引优化与 Redis 缓存设计；了解 Docker 容器化部署；\n"
            "有高并发系统经验者优先。职责：负责核心交易链路的设计与性能优化。"
        ),
    },
    {
        "name": "前端转后端低匹配",
        "expected": "low",
        "resume": (
            "李娜 ｜ 大专 · 视觉设计 ｜ 3 年前端开发\n"
            "技能：Vue3、TypeScript、Sass、Figma、Photoshop\n"
            "经历：某广告公司 前端开发（2022-2025）\n"
            "- 负责活动页 H5 开发，累计上线 40+ 个营销页面\n"
            "- 封装通用组件库 30 个，团队复用率提升 50%\n"
            "- 与设计师协作优化视觉还原度，验收通过率 95%"
        ),
        "jd": (
            "岗位：Python 后端开发工程师\n"
            "要求：精通 Python 与 Django/FastAPI；熟悉 MySQL 数据库设计与调优；\n"
            "掌握消息队列 RabbitMQ/Kafka；有微服务架构经验；\n"
            "职责：负责数据服务 API 开发与维护，参与后端架构演进。"
        ),
    },
    {
        "name": "数据岗中匹配",
        "expected": "medium",
        "resume": (
            "王强 ｜ 硕士 · 统计学 ｜ 2 年数据分析\n"
            "技能：SQL、Python(pandas)、Tableau、Excel、A/B 测试\n"
            "经历：某零售集团 数据分析师（2024-2026）\n"
            "- 搭建销售看板，覆盖 200 家门店，报表制作时间从 2 天缩短至 10 分钟\n"
            "- 通过购物篮分析推动货架调整，试点门店销售额环比提升 8%\n"
            "- 完成 12 次 A/B 实验设计与复盘，沉淀实验规范文档"
        ),
        "jd": (
            "岗位：商业数据分析师\n"
            "要求：1-3 年数据分析经验；精通 SQL 与 Python 数据处理；\n"
            "熟悉 Tableau/PowerBI 可视化；具备 A/B 测试与统计推断能力；\n"
            "有零售或电商行业经验优先。职责：支撑业务线的经营分析与策略建议。"
        ),
    },
]

# 改写覆盖度指标：rewritten 中出现数字即视为量化表达
_NUM_RE = re.compile(r"\d")
_STAR_WORDS = ("负责", "主导", "搭建", "设计", "推动", "实现", "优化", "完成", "构建")


def _jd_keywords(jd_text: str, top_n: int = 12) -> list[str]:
    """轻量 JD 关键词抽取：英文词 + 2-6 字中文词，按出现频次取 top N。"""
    words = re.findall(r"[A-Za-z][A-Za-z0-9+#.]{1,}|[\u4e00-\u9fa5]{2,6}", jd_text)
    stop = {"岗位", "要求", "职责", "熟悉", "精通", "掌握", "了解", "优先", "具备",
            "负责", "以上", "经验", "工作", "能力", "相关", "以及", "或"}
    freq: dict[str, int] = {}
    for w in words:
        if w in stop:
            continue
        freq[w] = freq.get(w, 0) + 1
    ranked = sorted(freq, key=lambda k: (-freq[k], len(k)))
    return ranked[:top_n]


def _coverage(keywords: list[str], texts: list[str]) -> float:
    """关键词命中率：任一命中（大小写不敏感）即算覆盖。"""
    if not keywords:
        return 0.0
    blob = "\n".join(texts).lower()
    hit = sum(1 for k in keywords if k.lower() in blob)
    return hit / len(keywords)


def _rewrite_metrics(diagnosis: dict, jd_text: str) -> dict:
    """改写覆盖度：建议数量、量化占比、JD 关键词命中率。"""
    sugg = diagnosis.get("suggestions") or []
    rewritten = [s.get("rewritten", "") for s in sugg if isinstance(s, dict)]
    quant = [t for t in rewritten if _NUM_RE.search(t)]
    action = [t for t in rewritten if any(w in t for w in _STAR_WORDS)]
    return {
        "num_suggestions": len(sugg),
        "quantified_ratio": len(quant) / len(sugg) if sugg else 0.0,
        "action_ratio": len(action) / len(sugg) if sugg else 0.0,
        "jd_keyword_coverage": _coverage(_jd_keywords(jd_text), rewritten + [
            s.get("reason", "") for s in sugg if isinstance(s, dict)
        ]),
    }


def _evidence_metrics(diagnosis: dict) -> dict:
    """证据引用质量（M11-A）：差距引用覆盖率 / 推断率 / 建议带据率。"""
    gaps = [g for g in diagnosis.get("gaps") or [] if isinstance(g, dict)]
    cited = [g for g in gaps if g.get("evidence")]
    inferred = [g for g in gaps if g.get("is_inferred")]
    sugg = [s for s in diagnosis.get("suggestions") or [] if isinstance(s, dict)]
    sugg_ev = [s for s in sugg if s.get("evidence_ids")]
    return {
        "gap_cited_ratio": len(cited) / len(gaps) if gaps else 0.0,
        "gap_inferred_ratio": len(inferred) / len(gaps) if gaps else 0.0,
        "sugg_evidence_ratio": len(sugg_ev) / len(sugg) if sugg else 0.0,
    }


async def run_case(case: dict, llm_config: dict | None) -> dict:
    """单用例单次诊断：返回 overall 分数 + 改写覆盖度 + 证据引用指标 + 耗时。"""
    t0 = time.time()
    diagnosis = await DiagnosisService().diagnose(case["resume"], case["jd"], llm_config=llm_config)
    elapsed = time.time() - t0
    if diagnosis.get("error"):
        return {"error": diagnosis["error"]}
    overall = (diagnosis.get("scores") or {}).get("overall", 0)
    return {
        "overall": overall,
        "num_gaps": len(diagnosis.get("gaps") or []),
        "elapsed": elapsed,
        **_rewrite_metrics(diagnosis, case["jd"]),
        **_evidence_metrics(diagnosis),
    }


async def _run_interactive_with_answers(case: dict, llm_config: dict, thread_id: str) -> dict:
    """在线完整链路：动态追问暂停时自动作答后恢复（M11-B 评估）。"""
    svc = DiagnosisService()
    r = await svc.diagnose(case["resume"], case["jd"], llm_config=llm_config, thread_id=thread_id)
    if r.get("waiting"):
        print(f"    ↳ 追问 {len(r['clarify_questions'])} 条，自动作答恢复")
        answers = {
            q["id"]: "主导过大促保障，峰值 QPS 12 万；带过 5 人小组；熟悉 Kubernetes 与 Kafka"
            for q in r["clarify_questions"]
        }
        r = await svc.diagnose(thread_id=thread_id, resume_answers=answers)
    await svc.release_thread(thread_id)
    return r


async def run_ablation(case: dict, llm_config: dict) -> list[dict]:
    """消融对比（M11-C）：完整 / 无RAG / 无refine / 在线追问，四变体各跑一次。"""
    from app.agents.nodes import gap_agent, scorer_agent

    async def _empty_pool(*a, **k):
        return []

    variants = [
        ("A 完整（RAG+refine）", "full"),
        ("B 无RAG证据", "no_rag"),
        ("C 无refine", "no_refine"),
        ("D 在线+自动追问", "interactive"),
    ]
    rows = []
    for name, mode in variants:
        print(f"  [消融] {name} ...")
        t0 = time.time()
        with ExitStack() as stack:
            if mode == "no_rag":
                # B 变体 = 完全移除证据层：检索禁用 + 证据校验禁用。
                # 只禁检索不够：glm-4-flash 在空池下仍会幻觉出恰好合法的
                # 证据 id（如 R1），filter_valid_ids 对着完整索引校验直接放行，
                # 导致消融失效（实测引用率虚高至 100%）。
                stack.enter_context(patch.object(gap_agent, "retrieval_pool", _empty_pool))
                stack.enter_context(patch.object(scorer_agent, "retrieval_pool", _empty_pool))
                stack.enter_context(patch.object(gap_agent, "filter_valid_ids", lambda idx, ids: []))
                stack.enter_context(patch.object(scorer_agent, "filter_valid_ids", lambda idx, ids: []))
            if mode == "no_refine":
                r = await DiagnosisService().diagnose(
                    case["resume"], case["jd"], llm_config=llm_config, enable_refine=False)
            elif mode == "interactive":
                r = await _run_interactive_with_answers(
                    case, llm_config, thread_id=f"eval-ablation-{mode}")
            else:
                r = await DiagnosisService().diagnose(case["resume"], case["jd"], llm_config=llm_config)
        if r.get("error"):
            print(f"    ✗ 失败：{r['error'][:120]}")
            rows.append({"name": name, "error": r["error"]})
            continue
        m = {
            "name": name,
            "overall": (r.get("scores") or {}).get("overall", 0),
            "elapsed": time.time() - t0,
            **_evidence_metrics(r),
            **{k: v for k, v in _rewrite_metrics(r, case["jd"]).items()},
            "num_gaps": len(r.get("gaps") or []),
            "questions": len(r.get("clarify_questions") or []),
        }
        rows.append(m)
        print(f"    ✓ overall={m['overall']} 引用率={m['gap_cited_ratio'] * 100:.0f}% "
              f"推断率={m['gap_inferred_ratio'] * 100:.0f}% 建议带据率={m['sugg_evidence_ratio'] * 100:.0f}%")
    return rows


# ---------------- 基线对比（论文实验）：完整链路 vs 全文直塞 ----------------
# E 变体 = 单次 LLM 调用、简历 JD 全文直塞、无证据接地/追问/精修，
# 等价于「把简历丢给通用 ChatGPT 让它评价」的典型用法。

class _BaselineGap(BaseModel):
    dimension: str
    description: str


class _BaselineSugg(BaseModel):
    original: str = ""
    rewritten: str
    reason: str = ""


class _BaselineDiag(BaseModel):
    scores: dict[str, float]
    gaps: list[_BaselineGap] = []
    suggestions: list[_BaselineSugg] = []


async def run_baseline_once(case: dict, llm_config: dict) -> dict:
    """全文直塞基线：单次调用产出与主链路同构的结果 dict，复用同一套指标。"""
    from app.agents.utils import call_llm_for_json

    prompt = (
        "你是资深的 HR 与简历顾问。请对比下面的简历与岗位 JD，评估简历与该岗位的匹配程度，"
        "指出差距并给出简历改写建议。只输出 JSON，不要输出其它文字，格式：\n"
        '{"scores": {"overall": 0-100 的整体匹配分}, '
        '"gaps": [{"dimension": "差距维度", "description": "差距描述"}], '
        '"suggestions": [{"original": "简历原文片段", "rewritten": "改写后的表述", "reason": "改写理由"}]}\n\n'
        f"【简历】\n{case['resume']}\n\n【岗位 JD】\n{case['jd']}"
    )
    t0 = time.time()
    out = await call_llm_for_json(prompt, _BaselineDiag, temperature=0.3, llm_config=llm_config)
    elapsed = time.time() - t0
    r = {
        "scores": {"overall": float((out.scores or {}).get("overall", 0))},
        "gaps": [g.model_dump() for g in out.gaps],
        "suggestions": [s.model_dump() for s in out.suggestions],
    }
    return {
        "overall": r["scores"]["overall"],
        "num_gaps": len(r["gaps"]),
        "elapsed": elapsed,
        **_rewrite_metrics(r, case["jd"]),
        **_evidence_metrics(r),
    }


async def run_baseline_compare(case: dict, llm_config: dict) -> list[dict]:
    """基线对比：A 完整链路 vs E 全文直塞，各跑一次。"""
    rows = []
    print(f"  [基线] A 完整链路（RAG+追问+refine）...")
    r_full = await run_case(case, llm_config)
    if "error" in r_full:
        print(f"    ✗ 失败：{r_full['error'][:120]}")
        rows.append({"name": case["name"], "plan": "A 完整链路", "error": r_full["error"]})
    else:
        rows.append({"name": case["name"], "plan": "A 完整链路", **r_full})
        print(f"    ✓ overall={r_full['overall']} 引用率={r_full['gap_cited_ratio'] * 100:.0f}%")

    print(f"  [基线] E 全文直塞（单次调用，无接地）...")
    r_base = await run_baseline_once(case, llm_config)
    if "error" in r_base:
        print(f"    ✗ 失败：{r_base['error'][:120]}")
        rows.append({"name": case["name"], "plan": "E 全文直塞", "error": r_base["error"]})
    else:
        rows.append({"name": case["name"], "plan": "E 全文直塞", **r_base})
        print(f"    ✓ overall={r_base['overall']} 引用率={r_base['gap_cited_ratio'] * 100:.0f}%")
    return rows


# ---------------- LLM-as-judge 评估（论文实验） ----------------
class _JudgeScore(BaseModel):
    relevance: float = Field(description="建议与岗位 JD 的相关度 0-10")
    specificity: float = Field(description="建议具体程度（有量化/可执行）0-10")
    faithfulness: float = Field(description="改写忠于简历原始经历、未编造 0-10")
    overall: float = Field(description="改写建议综合质量 0-10")
    comments: str = Field(default="", description="简要评语（≤50 字）")


async def judge_suggestions(case: dict, diagnosis: dict, llm_config: dict,
                            judge_config: dict | None = None) -> dict:
    """用强模型当裁判，对每条改写建议打分（4 维度 0-10 + 综合 + 评语）。

    judge_config 可独立指定更强模型（如 gpt-4o-mini / glm-4-plus）；
    不传则复用主链路 llm_config。"""
    from app.agents.utils import call_llm_for_json

    suggs = [s for s in (diagnosis.get("suggestions") or []) if isinstance(s, dict)]
    if not suggs:
        return {"judge_overall": 0.0, "judge_avg_relevance": 0.0,
                "judge_avg_specificity": 0.0, "judge_avg_faithfulness": 0.0,
                "judge_avg_overall": 0.0, "judge_comments": ""}

    suggestions_json = "\n".join(
        f"[{i + 1}] original: {s.get('original', '')[:80]}\n"
        f"      rewritten: {s.get('rewritten', '')[:120]}\n"
        f"      reason: {s.get('reason', '')[:80]}"
        for i, s in enumerate(suggs)
    )
    prompt = (
        "你是资深的简历评审专家。请对下面的改写建议进行评估，"
        "每条建议从 4 个维度打分（0-10 整数），并给出一条综合评语。\n"
        "评分标准：\n"
        "- relevance：改写内容是否紧扣岗位 JD 的要求\n"
        "- specificity：改写是否具体、有量化表达、可直接执行\n"
        "- faithfulness：改写是否忠于简历原始经历，未编造不存在的成就或经历\n"
        "- overall：综合质量分\n\n"
        f"【岗位 JD】\n{case['jd'][:500]}\n\n"
        f"【简历（原始经历摘要）】\n{case['resume'][:500]}\n\n"
        f"【改写建议】\n{suggestions_json}\n\n"
        "只输出 JSON，格式："
        '{"relevance":0-10,"specificity":0-10,"faithfulness":0-10,'
        '"overall":0-10,"comments":"一条综合评语"}'
    )
    cfg = judge_config or llm_config
    t0 = time.time()
    try:
        out = await call_llm_for_json(prompt, _JudgeScore, temperature=0.2, llm_config=cfg)
        elapsed = time.time() - t0
        r = {
            "judge_relevance": float(out.relevance),
            "judge_specificity": float(out.specificity),
            "judge_faithfulness": float(out.faithfulness),
            "judge_overall": float(out.overall),
            "judge_comments": out.comments,
            "judge_elapsed": elapsed,
        }
    except Exception as e:
        r = {"judge_error": str(e)[:200]}
    return r


async def run_judge_compare(case: dict, llm_config: dict,
                             judge_config: dict | None = None) -> list[dict]:
    """LLM-as-judge：A 完整链路 vs E 全文直塞，各自跑完后交给同一裁判打分。"""
    from app.agents.utils import call_llm_for_json

    async def _baseline_diag(case, llm_config):
        out = await call_llm_for_json(
            "你是资深的 HR。对比简历与 JD，输出 JSON：\n"
            '{"scores":{"overall":0-100},"gaps":[{"dimension":"","description":""}],'
            '"suggestions":[{"original":"","rewritten":"","reason":""}]}\n\n'
            f"【简历】\n{case['resume']}\n\n【岗位 JD】\n{case['jd']}",
            _BaselineDiag, temperature=0.3, llm_config=llm_config,
        )
        return {
            "scores": {"overall": float((out.scores or {}).get("overall", 0))},
            "gaps": [g.model_dump() for g in out.gaps],
            "suggestions": [s.model_dump() for s in out.suggestions],
        }

    rows = []
    for plan_name, plan_tag in [("完整链路", "A"), ("全文直塞", "E")]:
        print(f"  [judge] {plan_tag} {plan_name}：诊断 → 裁判打分")
        if plan_tag == "A":
            diag = await run_case(case, llm_config)
            if "error" in diag:
                rows.append({"plan": plan_tag, **diag})
                continue
            diag_for_judge = await DiagnosisService().diagnose(
                case["resume"], case["jd"], llm_config=llm_config)
            diag_dict = {
                "suggestions": diag_for_judge.get("suggestions") or [],
                "scores": diag_for_judge.get("scores") or {},
                "gaps": diag_for_judge.get("gaps") or [],
            }
        else:
            diag_dict = await _baseline_diag(case, llm_config)
            diag = {"overall": diag_dict["scores"]["overall"], "num_suggestions": len(diag_dict["suggestions"]),
                    "num_gaps": len(diag_dict["gaps"])}
        judge_r = await judge_suggestions(case, diag_dict, llm_config, judge_config)
        rows.append({"plan": plan_tag, "plan_name": plan_name,
                      **{k: v for k, v in diag.items() if k != "error"}, **judge_r})
        print(f"    ✓ judge_overall={judge_r.get('judge_overall', 'N/A')} "
              f"faithfulness={judge_r.get('judge_faithfulness', 'N/A')} "
              f"comments={judge_r.get('judge_comments', '')[:40]}")
    return rows


async def main():
    ap = argparse.ArgumentParser(description="ResuMatch AI 质量评估")
    ap.add_argument("--runs", type=int, default=2, help="每用例运行次数（默认 2）")
    ap.add_argument("--ablation", action="store_true", help="消融对比模式（完整/无RAG/无refine/在线追问）")
    ap.add_argument("--baseline", action="store_true", help="基线对比模式（完整链路 vs 全文直塞，3 用例各 1 轮）")
    ap.add_argument("--judge", action="store_true", help="LLM-as-judge：完整 vs 直塞各自跑完后交给同一裁判打分")
    ap.add_argument("--judge-model", default="", help="裁判模型（可独立于主链路模型，留空则复用 --model）")
    ap.add_argument("--case", type=int, default=1, help="消融用例序号（1-3，默认 1）")
    ap.add_argument("--api-key", default="", help="覆盖 .env 的 LLM Key")
    ap.add_argument("--base-url", default="", help="覆盖 .env 的 base_url")
    ap.add_argument("--model", default="", help="覆盖 .env 的模型名")
    ap.add_argument("--out", default="", help="报告路径（默认：消融→docs/消融评估报告.md，稳定性→docs/评估报告.md）")
    args = ap.parse_args()
    docs_dir = Path(__file__).resolve().parents[2] / "docs"
    default_out = docs_dir / (
        "消融评估报告.md" if args.ablation else
        "基线对比报告.md" if args.baseline else
        "裁判评估报告.md" if args.judge else
        "评估报告.md"
    )
    out_path = Path(args.out) if args.out else default_out

    llm_config = {k: v for k, v in {
        "api_key": args.api_key or settings.LLM_API_KEY,
        "base_url": args.base_url or settings.LLM_BASE_URL,
        "model": args.model or settings.LLM_MODEL,
    }.items() if v}
    if not llm_config.get("api_key"):
        sys.exit("未配置 LLM Key：请在 backend/.env 或 --api-key 提供")

    # ---------------- 消融模式：只跑变体对比 ----------------
    if args.ablation:
        case = CASES[max(0, min(args.case - 1, len(CASES) - 1))]
        print(f"消融评估：用例「{case['name']}」（模型 {llm_config.get('model', '默认')}）")
        rows = await run_ablation(case, llm_config)
        lines = [
            "# ResuMatch AI 消融评估报告（M11-C）",
            "",
            f"- 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- 模型：`{llm_config.get('model', '默认')}`｜用例：{case['name']}（期望匹配 {case['expected']}）",
            "- 说明：引用率=带证据原文引用的差距占比；推断率=无证据支撑差距占比；",
            "  建议带据率=改写建议标注依据证据 id 的占比。B 变体禁用证据检索与",
            "  证据校验（防止空池下模型幻觉 id 绕过校验），用于度量 RAG 证据接地的贡献。",
            "",
            "| 变体 | overall | 差距数 | 引用率 | 推断率 | 建议数 | 建议带据率 | 量化占比 | 追问数 | 耗时(s) |",
            "|---|---|---|---|---|---|---|---|---|---|",
        ]
        for m in rows:
            if "error" in m:
                lines.append(f"| {m['name']} | 失败 | - | - | - | - | - | - | - | - |")
                continue
            lines.append(
                f"| {m['name']} | {m['overall']} | {m['num_gaps']} "
                f"| {m['gap_cited_ratio'] * 100:.0f}% | {m['gap_inferred_ratio'] * 100:.0f}% "
                f"| {m['num_suggestions']} | {m['sugg_evidence_ratio'] * 100:.0f}% "
                f"| {m['quantified_ratio'] * 100:.0f}% | {m['questions']} | {m['elapsed']:.0f} |"
            )
        out_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        print(f"\n消融报告已写入 {out_path}")
        print("\n".join(lines))
        return

    # ---------------- 基线模式：完整链路 vs 全文直塞 ----------------
    if args.baseline:
        print(f"基线对比：{len(CASES)} 用例 × (完整链路 + 全文直塞)（模型 {llm_config.get('model', '默认')}）")
        all_rows = []
        for case in CASES:
            print(f"[用例] {case['name']}（期望匹配 {case['expected']}）")
            all_rows.extend(await run_baseline_compare(case, llm_config))
        lines = [
            "# ResuMatch AI 基线对比报告",
            "",
            f"- 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- 模型：`{llm_config.get('model', '默认')}`｜运行：{len(CASES)} 用例 × (A 完整链路 + E 全文直塞) 各 1 轮",
            "- 说明：E 全文直塞 = 单次 LLM 调用、简历 JD 全文直塞、无证据接地/动态追问/自省精修，",
            "  等价于「把简历丢给通用对话模型评价」的典型用法；引用率/带据率指标口径与消融报告一致。",
            "",
            "| 用例 | 方案 | overall | 差距数 | 引用率 | 推断率 | 建议数 | 建议带据率 | 量化占比 | JD 关键词命中 | 耗时(s) |",
            "|---|---|---|---|---|---|---|---|---|---|---|",
        ]
        agg: dict[str, list[float]] = {}
        for m in all_rows:
            if "error" in m:
                lines.append(f"| {m['name']} | {m['plan']} | 失败 | - | - | - | - | - | - | - | - |")
                continue
            lines.append(
                f"| {m['name']} | {m['plan']} | {m['overall']} | {m['num_gaps']} "
                f"| {m['gap_cited_ratio'] * 100:.0f}% | {m['gap_inferred_ratio'] * 100:.0f}% "
                f"| {m['num_suggestions']} | {m['sugg_evidence_ratio'] * 100:.0f}% "
                f"| {m['quantified_ratio'] * 100:.0f}% "
                f"| {m['jd_keyword_coverage'] * 100:.0f}% | {m['elapsed']:.0f} |"
            )
            agg.setdefault(m["plan"], []).append(m)
        lines += ["", "**汇总（均值）**", ""]
        for plan, rows in agg.items():
            n = len(rows)
            lines.append(
                f"- {plan}：overall 均值 {statistics.mean(r['overall'] for r in rows):.1f}，"
                f"引用率均值 {statistics.mean(r['gap_cited_ratio'] for r in rows) * 100:.0f}%，"
                f"建议带据率均值 {statistics.mean(r['sugg_evidence_ratio'] for r in rows) * 100:.0f}%"
                + (f"（n={n}）" if n > 1 else "（样本量小，仅示意；论文正式数据请扩大标注集）")
            )
        report = "\n".join(lines) + "\n"
        out_path.write_text(report, encoding="utf-8")
        print(f"\n基线对比报告已写入 {out_path}")
        print(report)
        return

    # ---------------- LLM-as-judge 模式 ----------------
    if args.judge:
        judge_config = None
        if args.judge_model:
            judge_config = {**llm_config, "model": args.judge_model}
        jmodel = judge_config.get("model") if judge_config else llm_config.get("model")
        print(f"LLM-as-judge：{len(CASES)} 用例 × (A 完整链路 + E 全文直塞) → 裁判打分")
        print(f"  诊断模型：{llm_config.get('model', '默认')}")
        print(f"  裁判模型：{jmodel}")
        all_rows = []
        for case in CASES:
            print(f"[用例] {case['name']}（期望匹配 {case['expected']}）")
            all_rows.extend(await run_judge_compare(case, llm_config, judge_config))
        lines = [
            "# ResuMatch AI LLM-as-Judge 评估报告",
            "",
            f"- 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"- 诊断模型：`{llm_config.get('model', '默认')}`｜裁判模型：`{jmodel}`",
            f"- 运行：{len(CASES)} 用例 × (A 完整链路 + E 全文直塞) 各 1 轮，裁判按建议质量打分",
            "- 说明：judge_relevance=改写与 JD 相关度；judge_specificity=具体/可执行/量化；",
            "  judge_faithfulness=忠于简历未编造（核心指标）；judge_overall=综合质量 0-10",
            "",
            "| 用例 | 方案 | overall | judge_relevance | judge_specificity | judge_faithfulness | judge_overall | 评语 |",
            "|---|---|---|---|---|---|---|---|",
        ]
        agg: dict[str, list[dict]] = {}
        for m in all_rows:
            plan = m.get("plan", "?")
            if "judge_error" in m:
                lines.append(f"| {m.get('name', '?')} | {plan} | {m.get('overall', '-')} | - | - | - | 裁判失败 | - |")
                continue
            lines.append(
                f"| {m.get('name', '?')} | {plan} | {m.get('overall', '-')} "
                f"| {m.get('judge_relevance', '-')} | {m.get('judge_specificity', '-')} "
                f"| {m.get('judge_faithfulness', '-')} | {m.get('judge_overall', '-')} "
                f"| {m.get('judge_comments', '')[:50]} |"
            )
            agg.setdefault(plan, []).append(m)
        lines += ["", "**裁判评分均值汇总**", ""]
        for plan, rows in agg.items():
            n = len(rows)
            valid = [r for r in rows if "judge_error" not in r]
            if not valid:
                lines.append(f"- {plan}：全部裁判失败")
                continue
            lines.append(
                f"- {plan}（n={n}）：judge_overall 均值 "
                f"{statistics.mean(r['judge_overall'] for r in valid):.1f}，"
                f"faithfulness 均值 "
                f"{statistics.mean(r['judge_faithfulness'] for r in valid):.1f}，"
                f"specificity 均值 "
                f"{statistics.mean(r['judge_specificity'] for r in valid):.1f}，"
                f"relevance 均值 "
                f"{statistics.mean(r['judge_relevance'] for r in valid):.1f}"
            )
        report = "\n".join(lines) + "\n"
        out_path.write_text(report, encoding="utf-8")
        print(f"\n裁判评估报告已写入 {out_path}")
        print(report)
        return

    print(f"评估开始：{len(CASES)} 用例 × {args.runs} 次（模型 {llm_config.get('model', '默认')}）")
    results: dict[str, list[dict]] = {}
    for case in CASES:
        runs = []
        for i in range(args.runs):
            print(f"  [{case['name']}] 第 {i + 1}/{args.runs} 次诊断...")
            r = await run_case(case, llm_config)
            if "error" in r:
                print(f"    ✗ 失败：{r['error'][:120]}")
            else:
                print(f"    ✓ overall={r['overall']} 建议 {r['num_suggestions']} 条")
            runs.append(r)
        results[case["name"]] = runs

    # ---------------- 汇总统计 ----------------
    lines = [
        "# ResuMatch AI 质量评估报告",
        "",
        f"- 时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"- 模型：`{llm_config.get('model', '默认')}`｜运行：{len(CASES)} 用例 × {args.runs} 次",
        "- 语义匹配口径：轻量词面重叠（未引入 embedding，LLM 链路为主通道）",
        "",
        "| 用例 | 期望匹配 | overall 均值 | 标准差 | 建议数均值 | 量化占比 | JD 关键词命中 |",
        "|---|---|---|---|---|---|---|",
    ]
    all_overalls: list[float] = []
    for case in CASES:
        runs = [r for r in results[case["name"]] if "error" not in r]
        n_err = args.runs - len(runs)
        if not runs:
            lines.append(f"| {case['name']} | {case['expected']} | 全部失败({n_err}) | - | - | - | - |")
            continue
        overalls = [r["overall"] for r in runs]
        all_overalls.extend(overalls)
        std = statistics.stdev(overalls) if len(overalls) > 1 else 0.0
        lines.append(
            f"| {case['name']} | {case['expected']} | {statistics.mean(overalls):.1f} "
            f"| {std:.1f} | {statistics.mean(r['num_suggestions'] for r in runs):.1f} "
            f"| {statistics.mean(r['quantified_ratio'] for r in runs) * 100:.0f}% "
            f"| {statistics.mean(r['jd_keyword_coverage'] for r in runs) * 100:.0f}% |"
        )
        if n_err:
            lines.append(f"  ⚠ 该用例有 {n_err} 次运行失败")

    if all_overalls:
        agg_std = statistics.stdev(all_overalls) if len(all_overalls) > 1 else 0.0
        lines += [
            "",
            f"**汇总**：overall 总体均值 {statistics.mean(all_overalls):.1f}，"
            f"总体标准差 {agg_std:.1f}（<10 视为稳定）。",
        ]
    else:
        lines += ["", "**汇总**：无成功运行，请检查 LLM 配置。"]

    report = "\n".join(lines) + "\n"
    out_path.write_text(report, encoding="utf-8")
    print(f"\n报告已写入 {out_path}")
    print(report)


if __name__ == "__main__":
    asyncio.run(main())
