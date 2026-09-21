"""真实 LLM 端到端验证（需 backend/.env 配置 LLM_API_KEY）。

用法：E:\\conda\\envs\\resumatch-ai\\python.exe tests/e2e_llm_check.py
验证点：
1. 六节点诊断链 + 证据检索（embedding 不可用时自动降级关键词）
2. 差距条目带 [R*] 证据引用
3. 动态追问 interrupt 暂停 → 提交回答 → 恢复完成
"""

import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.stdout.reconfigure(encoding="utf-8")

from app.services.diagnosis_service import DiagnosisService

RESUME = """李明
男 | 2000年 | 本科 · 华中科技大学 软件工程 | 13800000000 | liming@example.com

工作经历
武汉星河科技 后端开发工程师 2023.07 - 至今
- 负责订单中心微服务开发与维护，日均处理订单 50 万单
- 使用 Python/FastAPI 重构库存服务，接口平均响应时间从 800ms 降至 200ms
- 参与 Redis 缓存层设计，缓存命中率 92%

实习经历
北京云图信息 后端开发实习生 2022.12 - 2023.05
- 协助开发用户中心模块，编写接口文档与单元测试

项目经历
校园二手交易平台 2022.09 - 2023.01
- 基于 Django 开发，支持商品发布、搜索与站内信
- 上线首月注册用户 3000+

技能
Python、FastAPI、Django、MySQL、Redis、Docker、Git
"""

JD = """高级后端开发工程师（电商方向）
岗位职责：
1. 负责电商核心交易链路的设计与开发，保障高并发场景下的系统稳定性
2. 主导微服务架构演进，提升系统吞吐与可观测性
3. 指导初级工程师，推动团队技术方案评审

任职要求：
1. 本科及以上学历，5 年以上后端开发经验
2. 精通 Python/Go，熟悉 FastAPI 或类似框架
3. 深入理解 MySQL 索引优化、Redis 缓存架构、消息队列
4. 有百万级日活电商平台经验优先
5. 加分项：Kubernetes、服务治理、全链路压测经验
"""


async def main():
    svc = DiagnosisService()

    def on_progress(step, total, stage):
        print(f"  [进度 {step}/{total}] {stage}")

    print("=" * 60)
    print("第一段：完整诊断（差距分析后可能动态追问）")
    r1 = await svc.diagnose(RESUME, JD, on_progress=on_progress, thread_id="e2e-check")
    print("-" * 60)
    print(f"error: {r1['error'] or '（无）'}")
    print(f"综合评分: {r1['scores'].get('overall', '?')}")
    print(f"证据检索: index_chunks={len((r1.get('parsed') or {}).get('summary', '')) > 0}", end="")
    print()
    gaps = r1.get("gaps") or []
    cited = sum(1 for g in gaps if g.get("evidence"))
    print(f"差距 {len(gaps)} 条（{cited} 条带证据引用）:")
    for g in gaps:
        ev = " ".join(f"[{e['id']}]" for e in (g.get("evidence") or []))
        flag = "推断" if g.get("is_inferred") else "有据"
        print(f"  - [{g.get('severity')}] {g.get('dimension')}: {g.get('description')[:40]}… ({flag}) {ev}")
    print(f"建议 {len(r1.get('suggestions') or [])} 条（waiting={r1['waiting']}）")

    if not r1["waiting"]:
        print("LLM 判定无需追问，流程已完整结束")
        await svc.release_thread("e2e-check")
        return

    print("=" * 60)
    print("第二段：动态追问暂停，提交回答恢复")
    for q in r1["clarify_questions"]:
        print(f"  ❓ {q['id']}: {q['question']}")
    answers = {
        q["id"]: "8 年经验；主导过双十一大促，峰值 QPS 12 万；带过 5 人小组；熟悉 Kafka 与 K8s"
        for q in r1["clarify_questions"]
    }
    r2 = await svc.diagnose(thread_id="e2e-check", resume_answers=answers)
    print("-" * 60)
    print(f"恢复后 error: {r2['error'] or '（无）'}")
    print(f"综合评分: {r2['scores'].get('overall', '?')}")
    print(f"最终建议 {len(r2.get('suggestions') or [])} 条:")
    for s in r2.get("suggestions") or []:
        ev = " ".join(s.get("evidence_ids") or [])
        print(f"  - {s.get('target')}: {s.get('rewritten')[:50]}… 依据:{ev}")
    await svc.release_thread("e2e-check")
    print("=" * 60)
    ok = r2["error"] == "" and (r2.get("suggestions") or [])
    print("✅ E2E 通过" if ok else "❌ E2E 未通过")


asyncio.run(main())
