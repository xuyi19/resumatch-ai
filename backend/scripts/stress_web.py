"""Web 形态压力摸底（M17）：SSE 长连接并发上限 + SQLite WAL 并发写吞吐。

设计：
- 进程内起 uvicorn（port=0 随机端口），mock LLM 每节点延时 8s 拉长任务窗口，
  同一诊断任务上阶梯开 25/50/100/150 条 SSE 连接，测首包延迟（fan-out 响应）与进程内存；
- WAL 并发写：20/60/120 个工作循环并发插入 diagnosis_records（模拟进度节流写），
  测吞吐与锁/池错误。
- 客户端与服务端同进程（GIL 竞争使结果偏保守，作下界参考）。

隔离：DB/照片目录指到 tests/.tmp/stress/，不碰运行时 data/（同 conftest 约定）。
用法（backend 目录下）：python scripts/stress_web.py
"""
import asyncio
import ctypes
import os
import statistics
import sys
import time
from pathlib import Path
from unittest.mock import patch
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

# ---- 隔离先行：环境变量必须先于任何 app 模块导入 ----
_TMP = Path(__file__).resolve().parent.parent / "tests" / ".tmp" / "stress"
_TMP.mkdir(parents=True, exist_ok=True)
os.environ["DB_URL"] = f"sqlite+aiosqlite:///{(_TMP / 'stress.db').as_posix()}"
os.environ["PHOTOS_DIR"] = str(_TMP / "photos")

import httpx  # noqa: E402
import uvicorn  # noqa: E402

from app.core.db import AsyncSessionLocal, Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import entities  # noqa: F401,E402
from app.models.entities import DiagnosisRecord  # noqa: E402
from app.services.live_pipeline_service import LivePipelineService  # noqa: E402

# 必须在 engine 创建（echo=True 会强制重设 INFO）之后压掉 SQL 日志刷屏
import logging  # noqa: E402
logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

LLM_SLEEP = 8.0            # mock LLM 每节点耗时（s），enable_refine=False 共 5 节点 ≈ 40s
SSE_WAVES = (25, 50, 100, 150)
SSE_HOLD = 7.0             # 每波连接保持时长（s）
WRITE_WORKERS = (20, 60, 120)
WRITE_HOLD = 8.0


class FakeResult:
    def __init__(self, payload: dict):
        self._payload = payload

    def __getattr__(self, name):
        try:
            value = self._payload[name]
        except KeyError:
            raise AttributeError(name)
        if isinstance(value, list):
            return [FakeResult(v) if isinstance(v, dict) else v for v in value]
        return value

    def model_dump(self):
        return self._payload


def _payloads():
    return {
        "ParsedResume": FakeResult({
            "education": ["本科"], "experience": ["3 年后端"], "projects": ["推荐系统"],
            "skills": ["Python"], "summary": "后端工程师",
        }),
        "JobAnalysis": FakeResult({
            "requirements": {
                "hard_skills": ["Python"], "soft_skills": [], "experience_years": "3-5年",
                "education": "本科", "keywords": ["Python"], "responsibilities": ["开发"],
            },
            "summary": "Python 后端岗",
        }),
        "ResumeScores": FakeResult({
            "completeness": {"score": 70, "comment": "完整"},
            "quantification": {"score": 60, "comment": "一般"},
            "star_structure": {"score": 65, "comment": "尚可"},
            "skill_match": {"score": 80, "comment": "匹配"},
            "achievement": {"score": 55, "comment": "待补"},
            "readability": {"score": 75, "comment": "清晰"},
            "overall": 68,
        }),
        "GapAnalysis": FakeResult({
            "gaps": [{"dimension": "技能", "description": "缺 MySQL 深度", "severity": "medium"}],
            "summary": "匹配度尚可",
        }),
        "ClarifyPlan": FakeResult({"questions": []}),
        "RewriteResult": FakeResult({
            "suggestions": [{"target": "项目", "original": "做了推荐系统",
                             "rewritten": "为 X 构建…", "reason": "补量化"}],
            "overall_advice": "补充量化数据",
        }),
    }


def rss_mb() -> float:
    """当前进程工作集内存（Windows psapi，失败返回 -1）。"""
    if sys.platform != "win32":
        return -1.0

    class PMC(ctypes.Structure):
        _fields_ = [
            ("cb", ctypes.c_ulong), ("PageFaultCount", ctypes.c_ulong),
            ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t), ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    pmc = PMC()
    pmc.cb = ctypes.sizeof(PMC)
    kernel32 = ctypes.windll.kernel32
    kernel32.GetCurrentProcess.restype = ctypes.c_void_p  # 64 位伪句柄需按指针宽度取
    handle = kernel32.GetCurrentProcess()
    if ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.c_void_p(handle), ctypes.byref(pmc), pmc.cb):
        return pmc.WorkingSetSize / 1024 / 1024
    return -1.0


async def sse_client(client: httpx.AsyncClient, url: str, out: dict):
    """单条 SSE 连接：记录首包延迟与收到的事件数。"""
    first = None
    events = 0
    try:
        async with client.stream("GET", url, timeout=httpx.Timeout(120, read=120)) as resp:
            if resp.status_code != 200:
                out["errors"] += 1
                return
            async for line in resp.aiter_lines():
                if line.startswith("data:"):
                    events += 1
                    if first is None:
                        first = time.perf_counter()
    except Exception:
        out["errors"] += 1
    finally:
        if first is not None:
            out["first_data"].append(first)
        out["events"] += events
        out["ok"] += 1


async def write_worker(stop: asyncio.Event, errors: list) -> int:
    """并发写工作循环：插入 + 提交，直到 stop。"""
    n = 0
    while not stop.is_set():
        try:
            async with AsyncSessionLocal() as session:
                session.add(DiagnosisRecord(
                    task_id=uuid4().hex, keyword="stress", status="success",
                ))
                await session.commit()
            n += 1
        except Exception as e:
            errors.append(f"{type(e).__name__}: {e}")
            await asyncio.sleep(0.05)
    return n


def _pct(values: list, p: float) -> float:
    if not values:
        return -1.0
    s = sorted(values)
    return s[min(len(s) - 1, int(len(s) * p))]


async def main():
    t0 = time.perf_counter()
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # 进程内起服务（随机端口）
    config = uvicorn.Config(app, host="127.0.0.1", port=0, log_level="warning")
    server = uvicorn.Server(config)
    server_task = asyncio.create_task(server.serve())
    while not server.started:
        await asyncio.sleep(0.05)
    port = server.servers[0].sockets[0].getsockname()[1]
    base = f"http://127.0.0.1:{port}/api/v1"
    print(f"[stress] 服务已启动 :{port}（进程内）  内存基线 {rss_mb():.0f} MB")

    limits = httpx.Limits(max_connections=400, max_keepalive_connections=400)
    print("\n===== 阶段 1：SSE 长连接并发（单任务，mock LLM 每节点 8s）=====")
    print(f"{'并发数':>6} | {'连上':>4} | {'首包p50(s)':>10} | {'首包p95(s)':>10} | "
          f"{'事件数':>6} | {'错误':>4} | {'内存(MB)':>8}")

    payloads = _payloads()

    async def fake_call(prompt, schema, **kwargs):
        await asyncio.sleep(LLM_SLEEP)
        return payloads[schema.__name__]

    with patch("app.agents.nodes.parser_agent.call_llm_for_json", side_effect=fake_call), \
         patch("app.agents.nodes.job_analyze_agent.call_llm_for_json", side_effect=fake_call), \
         patch("app.agents.nodes.scorer_agent.call_llm_for_json", side_effect=fake_call), \
         patch("app.agents.nodes.gap_agent.call_llm_for_json", side_effect=fake_call), \
         patch("app.agents.nodes.clarify_agent.call_llm_for_json", side_effect=fake_call), \
         patch("app.agents.nodes.rewriter_agent.call_llm_for_json", side_effect=fake_call):
        task_id = LivePipelineService.create_task(resume_name="压测", owner_id="local")
        diag = asyncio.create_task(LivePipelineService.run(
            task_id, "简历文本", "这是一段用于压力摸底的岗位描述文本，长度超过二十个字。",
            enable_refine=False,
        ))
        await asyncio.sleep(0.5)  # 让任务进入 running
        url = f"{base}/live/stream/{task_id}"

        async with httpx.AsyncClient(limits=limits) as client:
            for k in SSE_WAVES:
                out = {"first_data": [], "events": 0, "errors": 0, "ok": 0}
                wave_start = time.perf_counter()
                tasks = [asyncio.create_task(sse_client(client, url, out)) for _ in range(k)]
                await asyncio.sleep(SSE_HOLD)
                for t in tasks:
                    t.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                firsts = [t - wave_start for t in out["first_data"]]
                print(f"{k:>6} | {out['ok']:>4} | {_pct(firsts, 0.5):>10.2f} | "
                      f"{_pct(firsts, 0.95):>10.2f} | {out['events']:>6} | "
                      f"{out['errors']:>4} | {rss_mb():>8.0f}")

        # 等任务收尾
        try:
            await asyncio.wait_for(asyncio.shield(diag), timeout=60)
        except Exception:
            diag.cancel()

    print("\n===== 阶段 2：SQLite WAL 并发写（模拟进度节流写）=====")
    print(f"{'工作循环':>6} | {'时长(s)':>6} | {'成功写':>8} | {'ops/s':>8} | {'错误':>6}")
    for n in WRITE_WORKERS:
        errors: list[str] = []
        stop = asyncio.Event()
        start = time.perf_counter()
        workers = [asyncio.create_task(write_worker(stop, errors)) for _ in range(n)]
        await asyncio.sleep(WRITE_HOLD)
        stop.set()
        counts = await asyncio.gather(*workers, return_exceptions=True)
        elapsed = time.perf_counter() - start
        total = sum(c for c in counts if isinstance(c, int))
        print(f"{n:>6} | {elapsed:>6.1f} | {total:>8} | {total / elapsed:>8.0f} | {len(errors):>6}")
        if errors:
            print(f"        错误样例: {errors[0][:160]}")

    await server.shutdown()
    server_task.cancel()
    print(f"\n[stress] 完成，总耗时 {time.perf_counter() - t0:.0f}s；数据落在 {_TMP}")


if __name__ == "__main__":
    asyncio.run(main())
