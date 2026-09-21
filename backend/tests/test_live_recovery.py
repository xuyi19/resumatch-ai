"""M16 跨重启恢复集成测试（mock LLM，不联网）：
waiting_clarify 任务的问题/上下文落库 → 内存任务表清空（模拟进程重启）→
从 DB 重建并经 Command(resume) 续跑完成。图状态快照由 SqliteSaver 文件提供。"""
from unittest.mock import patch

import pytest
from sqlalchemy import select

from app.core.db import AsyncSessionLocal
from app.models.entities import DiagnosisRecord
from app.services import live_pipeline_service
from app.services.live_pipeline_service import LivePipelineService

# 内存任务表是模块级 dict（非类属性），模拟重启直接清空它
TASKS = live_pipeline_service.TASKS


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
        "ClarifyPlan": FakeResult({
            "questions": [{"id": "q1", "gap": "缺量化", "question": "项目 QPS 是多少？", "hint": ""}],
        }),
        "RewriteResult": FakeResult({
            "suggestions": [{"target": "项目", "original": "做了推荐系统",
                             "rewritten": "为 X 构建…", "reason": "补量化"}],
            "overall_advice": "补充量化数据",
        }),
    }


@pytest.fixture
def mock_llm():
    payloads = _payloads()

    async def fake_call(prompt, schema, **kwargs):
        return payloads[schema.__name__]

    with patch("app.agents.nodes.parser_agent.call_llm_for_json", side_effect=fake_call), \
         patch("app.agents.nodes.job_analyze_agent.call_llm_for_json", side_effect=fake_call), \
         patch("app.agents.nodes.scorer_agent.call_llm_for_json", side_effect=fake_call), \
         patch("app.agents.nodes.gap_agent.call_llm_for_json", side_effect=fake_call), \
         patch("app.agents.nodes.clarify_agent.call_llm_for_json", side_effect=fake_call), \
         patch("app.agents.nodes.rewriter_agent.call_llm_for_json", side_effect=fake_call):
        yield


async def _db_record(task_id: str) -> DiagnosisRecord | None:
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(DiagnosisRecord).where(DiagnosisRecord.task_id == task_id)
        )
        return res.scalar_one_or_none()


@pytest.mark.asyncio
async def test_waiting_persisted_and_resume_after_restart(mock_llm):
    """waiting 快照落库 → 模拟重启清内存 → DB 重建 → resume 续跑成功落库"""
    task_id = LivePipelineService.create_task(resume_name="测试简历", owner_id="local")
    await LivePipelineService.run(task_id, "简历文本", "JD文本")

    task = LivePipelineService.get_task(task_id)
    assert task["status"] == "waiting_clarify"

    # DB 快照：状态、问题列表、恢复上下文齐全
    rec = await _db_record(task_id)
    assert rec.status == "waiting_clarify"
    assert rec.questions and rec.questions[0]["id"] == "q1"
    assert rec.clarify_ctx["jd_text"] == "JD文本"
    assert "enable_refine" in rec.clarify_ctx

    # ★ 模拟进程重启：内存任务表清空
    TASKS.clear()
    assert LivePipelineService.get_task(task_id) is None

    # 提交回答：resume 应自动从 DB 重建任务并续跑
    await LivePipelineService.resume(task_id, {"q1": "峰值 QPS 3000，日活 5 万"})
    task = LivePipelineService.get_task(task_id)
    assert task["status"] == "success"
    assert task["result"]["diagnosis"]["suggestions"], "恢复后应产出改写建议"

    rec = await _db_record(task_id)
    assert rec.status == "success"
    assert rec.result["diagnosis"]["suggestions"]

    await DiagnosisService_cleanup(task_id)


@pytest.mark.asyncio
async def test_recover_waiting_tasks_on_startup(mock_llm):
    """启动补偿：DB 中的 waiting 任务重建进内存表（服务重启后前端立即可见可答）"""
    task_id = LivePipelineService.create_task(resume_name="测试简历", owner_id="local")
    await LivePipelineService.run(task_id, "简历文本", "JD文本")
    TASKS.clear()

    restored = await LivePipelineService.recover_waiting_tasks()
    assert restored >= 1  # 至少恢复本用例刚产生的 waiting 任务（.tmp 库跨运行留存不计数干扰）
    task = LivePipelineService.get_task(task_id)
    assert task["status"] == "waiting_clarify"
    assert task["questions"][0]["id"] == "q1"
    assert task["jd_text"] == "JD文本"

    # 重建后的任务可直接 resume 完成
    await LivePipelineService.resume(task_id, {"q1": "QPS 1000"})
    assert LivePipelineService.get_task(task_id)["status"] == "success"

    await DiagnosisService_cleanup(task_id)


@pytest.mark.asyncio
async def test_recover_legacy_waiting_without_ctx_marks_failed():
    """无 clarify_ctx 的历史 waiting 任务（老版本产生）恢复不了 → 标记失败而非悬置"""
    from uuid import uuid4

    task_id = uuid4().hex  # 随机 id：.tmp 测试库跨运行留存，避免 UNIQUE 冲突
    async with AsyncSessionLocal() as session:
        rec = DiagnosisRecord(task_id=task_id, keyword="测试", owner_id="local",
                              status="waiting_clarify", questions=[{"id": "q1"}])
        session.add(rec)
        await session.commit()

    await LivePipelineService.recover_waiting_tasks()

    rec = await _db_record(task_id)
    assert rec.status == "failed"
    assert "上下文丢失" in rec.error


async def DiagnosisService_cleanup(task_id: str):
    from app.services.diagnosis_service import DiagnosisService

    await DiagnosisService().release_thread(task_id)
