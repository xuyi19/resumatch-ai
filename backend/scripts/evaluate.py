"""质量评估脚本（M6 基础 + M11-C 扩展）：简历-JD 标注集多次诊断，统计评分稳定性、
改写覆盖度与证据引用质量；支持消融对比（完整 / 无RAG / 无refine / 在线追问）。

用法（backend 目录下）：
    python scripts/evaluate.py                     # 稳定性：3 用例 × 2 次
    python scripts/evaluate.py --ablation          # 消融对比：4 变体 × 用例1
    python scripts/evaluate.py --ablation --case 2 # 指定消融用例
    python scripts/evaluate.py --api-key sk-xxx --model deepseek-chat

产出：docs/评估报告.md（评分均值/标准差、改写覆盖度、证据引用覆盖/推断率、消融表）

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


async def main():
    ap = argparse.ArgumentParser(description="ResuMatch AI 质量评估")
    ap.add_argument("--runs", type=int, default=2, help="每用例运行次数（默认 2）")
    ap.add_argument("--ablation", action="store_true", help="消融对比模式（完整/无RAG/无refine/在线追问）")
    ap.add_argument("--case", type=int, default=1, help="消融用例序号（1-3，默认 1）")
    ap.add_argument("--api-key", default="", help="覆盖 .env 的 LLM Key")
    ap.add_argument("--base-url", default="", help="覆盖 .env 的 base_url")
    ap.add_argument("--model", default="", help="覆盖 .env 的模型名")
    ap.add_argument("--out", default="", help="报告路径（默认：消融→docs/消融评估报告.md，稳定性→docs/评估报告.md）")
    args = ap.parse_args()
    docs_dir = Path(__file__).resolve().parents[2] / "docs"
    default_out = docs_dir / ("消融评估报告.md" if args.ablation else "评估报告.md")
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
