"""质量评估脚本（M6）：简历-JD 标注集多次诊断，统计评分稳定性与改写覆盖度。

用法（backend 目录下）：
    python scripts/evaluate.py                     # 用 .env 的 LLM 配置，每用例跑 2 次
    python scripts/evaluate.py --runs 3            # 多跑几轮看稳定性
    python scripts/evaluate.py --api-key sk-xxx --model deepseek-chat

产出：docs/评估报告.md（评分均值/标准差、改写覆盖度、JD 关键词命中）

说明：语义匹配采用轻量词面重叠指标（不引入 embedding/torch，
避免桌面版体积膨胀；LLM 链路本身即语义匹配主通道）。
"""
import argparse
import asyncio
import re
import statistics
import sys
from datetime import datetime
from pathlib import Path

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


async def run_case(case: dict, llm_config: dict | None) -> dict:
    """单用例单次诊断：返回 overall 分数 + 改写覆盖度指标 + 错误信息。"""
    diagnosis = await DiagnosisService().diagnose(case["resume"], case["jd"], llm_config=llm_config)
    if diagnosis.get("error"):
        return {"error": diagnosis["error"]}
    overall = (diagnosis.get("scores") or {}).get("overall", 0)
    return {"overall": overall, **_rewrite_metrics(diagnosis, case["jd"])}


async def main():
    ap = argparse.ArgumentParser(description="ResuMatch AI 质量评估")
    ap.add_argument("--runs", type=int, default=2, help="每用例运行次数（默认 2）")
    ap.add_argument("--api-key", default="", help="覆盖 .env 的 LLM Key")
    ap.add_argument("--base-url", default="", help="覆盖 .env 的 base_url")
    ap.add_argument("--model", default="", help="覆盖 .env 的模型名")
    ap.add_argument("--out", default=str(Path(__file__).resolve().parents[2] / "docs" / "评估报告.md"))
    args = ap.parse_args()

    llm_config = {k: v for k, v in {
        "api_key": args.api_key or settings.LLM_API_KEY,
        "base_url": args.base_url or settings.LLM_BASE_URL,
        "model": args.model or settings.LLM_MODEL,
    }.items() if v}
    if not llm_config.get("api_key"):
        sys.exit("未配置 LLM Key：请在 backend/.env 或 --api-key 提供")

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
    Path(args.out).write_text(report, encoding="utf-8")
    print(f"\n报告已写入 {args.out}")
    print(report)


if __name__ == "__main__":
    asyncio.run(main())
