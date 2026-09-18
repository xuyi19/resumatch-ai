"""诊断工作流集成测试（mock LLM，不联网）"""
from unittest.mock import patch

import pytest

from app.services.diagnosis_service import DiagnosisService


class FakeResult:
    """模拟 call_llm_for_json 返回的 pydantic 对象（属性 + model_dump），
    嵌套 dict 列表（gaps/suggestions）同样暴露 .model_dump()"""

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


def _fake_payloads():
    """各节点应返回的 schema 化数据，按调用顺序排列：
    parser → job_analyze → scorer → gap → rewriter
    （parser 与 job_analyze 并行，顺序可能互换，见 payload 匹配逻辑）
    """
    return {
        "ParsedResume": FakeResult({
            "education": ["本科 · 计算机科学"],
            "experience": ["3 年 Python 后端"],
            "projects": ["推荐系统"],
            "skills": ["Python", "FastAPI"],
            "summary": "后端工程师",
        }),
        "JobAnalysis": FakeResult({
            "requirements": {
                "hard_skills": ["Python", "MySQL"],
                "soft_skills": ["沟通"],
                "experience_years": "3-5年",
                "education": "本科",
                "keywords": ["Python"],
                "responsibilities": ["开发"],
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
            "gaps": [
                {"dimension": "技能", "description": "缺 MySQL 深度", "severity": "medium"},
            ],
            "summary": "整体匹配度尚可",
        }),
        "RewriteResult": FakeResult({
            "suggestions": [
                {"target": "项目", "original": "做了推荐系统",
                 "rewritten": "为 X 构建…", "reason": "补量化"},
            ],
            "overall_advice": "补充量化数据",
        }),
    }


@pytest.fixture
def mock_llm():
    """按 schema 类名分发 mock 结果；记录调用次数。"""
    payloads = _fake_payloads()
    calls = []

    async def fake_call(prompt, schema, **kwargs):
        calls.append(schema.__name__)
        return payloads[schema.__name__]

    with patch("app.agents.nodes.parser_agent.call_llm_for_json", side_effect=fake_call), \
         patch("app.agents.nodes.job_analyze_agent.call_llm_for_json", side_effect=fake_call), \
         patch("app.agents.nodes.scorer_agent.call_llm_for_json", side_effect=fake_call), \
         patch("app.agents.nodes.gap_agent.call_llm_for_json", side_effect=fake_call), \
         patch("app.agents.nodes.rewriter_agent.call_llm_for_json", side_effect=fake_call):
        yield calls


@pytest.mark.asyncio
async def test_diagnose_full_flow(mock_llm):
    """5 个节点全部执行，结果结构完整，进度回调逐节点触发"""
    progress_events = []

    result = await DiagnosisService().diagnose(
        "学历：本科 工作年限：3年 技能：Python",
        "岗位：Python 后端 要求：FastAPI",
        on_progress=lambda step, total, stage: progress_events.append((step, total, stage)),
    )

    # 5 个节点全部被调用（不关心并行分支的先后）
    assert result["error"] == "", f"诊断出错: {result['error']}"
    assert sorted(mock_llm) == [
        "GapAnalysis", "JobAnalysis", "ParsedResume", "ResumeScores", "RewriteResult",
    ]
    assert result["parsed"]["summary"] == "后端工程师"
    assert result["job_analysis"]["summary"] == "Python 后端岗"
    assert result["scores"]["overall"] == 68
    assert len(result["gaps"]) == 1
    assert len(result["suggestions"]) == 1
    assert result["overall_advice"] == "补充量化数据"

    # 进度回调：5 次，覆盖全部阶段
    assert len(progress_events) == 5
    assert progress_events[-1][0] == 5
    stages = [e[2] for e in progress_events]
    assert set(stages) == {"解析简历", "解析岗位", "六维评分", "差距分析", "改写建议"}


@pytest.mark.asyncio
async def test_diagnose_parser_failure_circuit_breaks():
    """parser 失败 → 熔断，下游（scorer/gap/rewriter）不执行"""
    calls = []
    payloads = _fake_payloads()

    def make_call(name: str):
        async def _call(prompt, schema, **kwargs):
            calls.append(schema.__name__)
            if schema.__name__ == "ParsedResume" and name == "parser":
                raise RuntimeError("模拟 LLM 故障")
            return payloads[schema.__name__]
        return _call

    with patch("app.agents.nodes.parser_agent.call_llm_for_json",
               side_effect=make_call("parser")), \
         patch("app.agents.nodes.job_analyze_agent.call_llm_for_json",
               side_effect=make_call("job_analyze")), \
         patch("app.agents.nodes.scorer_agent.call_llm_for_json",
               side_effect=make_call("scorer")), \
         patch("app.agents.nodes.gap_agent.call_llm_for_json",
               side_effect=make_call("gap")), \
         patch("app.agents.nodes.rewriter_agent.call_llm_for_json",
               side_effect=make_call("rewriter")):
        result = await DiagnosisService().diagnose("简历", "JD")

    assert "解析失败" in result["error"]
    # 熔断后只有 parser（失败）和并行的 job_analyze 执行
    assert sorted(calls) == ["JobAnalysis", "ParsedResume"]
    assert result["scores"] == {}


@pytest.mark.asyncio
async def test_diagnose_both_branches_fail_no_crash():
    """parser 与 job_analyze 同一步都失败：error 合并而非 InvalidUpdateError 崩溃"""
    payloads = _fake_payloads()

    async def failing(prompt, schema, **kwargs):
        raise RuntimeError("模拟 LLM 全线故障")

    with patch("app.agents.nodes.parser_agent.call_llm_for_json", side_effect=failing), \
         patch("app.agents.nodes.job_analyze_agent.call_llm_for_json", side_effect=failing), \
         patch("app.agents.nodes.scorer_agent.call_llm_for_json",
               side_effect=lambda p, s, **k: payloads[s.__name__]), \
         patch("app.agents.nodes.gap_agent.call_llm_for_json",
               side_effect=lambda p, s, **k: payloads[s.__name__]), \
         patch("app.agents.nodes.rewriter_agent.call_llm_for_json",
               side_effect=lambda p, s, **k: payloads[s.__name__]):
        result = await DiagnosisService().diagnose("简历", "JD")

    # 两个分支的错误都写入 state，保留其一，不抛 InvalidUpdateError
    assert result["error"] in ("解析失败: 模拟 LLM 全线故障", "JD 解析失败: 模拟 LLM 全线故障")
    assert result["scores"] == {}
