"""M64 刷题工坊测试：AI 出题 → 交卷判定 → 战报/错题本 + owner 会话隔离 + 失败路径。

用 uuid 会话（X-Session-Id 头）做 owner 隔离（同 test_job_library.py 惯例）；
LLM 调用统一 monkeypatch quiz 模块命名空间的 call_llm_for_json（from-import 直引，
需 setattr 到 quiz 模块），不真实调用模型。
"""

from uuid import uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1 import quiz as quiz_mod
from app.api.v1.quiz import CodeJudge, QuizPlan
from app.core.config import settings
from app.main import app


@pytest.fixture
async def client(monkeypatch):
    # web 态让 X-Session-Id 头生效（桌面态 owner 恒为 local，无法测隔离）
    monkeypatch.setattr(settings, "APP_MODE", "web")
    monkeypatch.setattr(quiz_mod, "call_llm_for_json", _fake_call_llm)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _sid() -> dict:
    return {"X-Session-Id": f"qz-{uuid4().hex[:12]}"}


def _fake_questions() -> list[dict]:
    """2 道确定性题（choice/logic）+ 1 道编程思路题。"""
    return [
        {"id": "q1", "qtype": "choice", "stem": "Python 字典按键查找的平均时间复杂度是？",
         "options": ["O(n)", "O(1)", "O(log n)", "O(n log n)"], "answer": 1,
         "analysis": "字典基于哈希表实现，键查找平均 O(1)。"},
        {"id": "q2", "qtype": "logic", "stem": "数列 2, 4, 6, 8 的下一项是？",
         "options": ["9", "10", "11", "12"], "answer": 1, "analysis": "公差为 2 的等差数列。"},
        {"id": "q3", "qtype": "code", "stem": "统计一段文本中出现次数最多的词，说明思路。",
         "options": [], "answer": "分词后哈希表计数，遍历取最大值，O(n)。",
         "analysis": "考察哈希计数思想与复杂度分析。"},
    ]


async def _fake_call_llm(prompt, model_cls, **kwargs):
    if model_cls is QuizPlan:
        return QuizPlan.model_validate({"questions": _fake_questions()})
    if model_cls is quiz_mod.CodeJudge:
        return CodeJudge(correct=True, comment="思路正确，覆盖主要要点")
    raise AssertionError(f"未预期的模型类型 {model_cls}")


async def _generate(client, headers, **overrides) -> dict:
    body = {"direction": "Python 后端", "llm_config": {}}
    body.update(overrides)
    resp = await client.post("/api/v1/quiz/generate", json=body, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


async def test_generate_and_submit_full_flow(client, monkeypatch):
    """出题→交卷全链路：题面防作弊剥离、全对 100 分、错题本 0 条、GET 完整回放。"""
    captured = {}

    async def _spy(prompt, model_cls, **kwargs):
        captured["prompt"] = prompt
        return await _fake_call_llm(prompt, model_cls, **kwargs)

    monkeypatch.setattr(quiz_mod, "call_llm_for_json", _spy)
    hd = _sid()
    data = await _generate(client, hd)

    assert data["task_id"].startswith("qz-")
    assert data["count"] == 3
    # 防作弊：返回题面不含 answer/analysis
    assert len(data["questions"]) == 3
    for q in data["questions"]:
        assert "answer" not in q and "analysis" not in q
        assert q["stem"] and q["qtype"]
    assert data["questions"][2]["options"] == []  # 编程题选项为空
    # 红线：出题 prompt 带禁编造约束
    assert "禁止编造" in captured["prompt"]

    # 进行中 GET：剥离答案题面
    got = (await client.get(f"/api/v1/quiz/{data['task_id']}", headers=hd)).json()
    assert got["exists"] is True and got["status"] == "ongoing"
    assert "answer" not in got["questions"][0] and got["report"] is None
    assert got["direction"] == "Python 后端"

    # 交卷：全对（含编程题判对）
    resp = await client.post(
        f"/api/v1/quiz/{data['task_id']}/submit",
        json={"answers": {"q1": 1, "q2": 1, "q3": "分词后哈希表计数取最大值"}, "llm_config": {}},
        headers=hd,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["score"] == 100 and body["correct_count"] == 3 and body["total"] == 3
    assert body["wrong_ids"] == []
    by_qid = {r["qid"]: r for r in body["results"]}
    assert by_qid["q1"]["answer"] == 1 and by_qid["q1"]["analysis"]  # 交卷后带答案+解析
    assert by_qid["q3"]["correct"] is True and "思路正确" in by_qid["q3"]["comment"]

    # 会话状态：finished + 战报落库
    got = (await client.get(f"/api/v1/quiz/{data['task_id']}", headers=hd)).json()
    assert got["status"] == "finished"
    assert "answer" in got["questions"][0] and "analysis" in got["questions"][0]
    assert got["report"]["score"] == 100
    assert len(got["answers"]) == 3 and all(a["correct"] is True for a in got["answers"])

    # 会话列表：带方向/得分
    sessions = (await client.get("/api/v1/quiz/sessions", headers=hd)).json()
    hit = next(s for s in sessions if s["task_id"] == data["task_id"])
    assert hit["status"] == "finished" and hit["score"] == 100 and hit["total"] == 3

    # 错题本：全对 → 空
    wb = (await client.get("/api/v1/quiz/wrongbook", headers=hd)).json()
    assert wb["items"] == []


async def test_wrong_answer_feeds_wrongbook(client):
    """答错 1 题：wrong_ids 收录、错题本含方向与解析、得分 2/3→67。"""
    hd = _sid()
    data = await _generate(client, hd)
    resp = await client.post(
        f"/api/v1/quiz/{data['task_id']}/submit",
        json={"answers": {"q1": 0, "q2": 1, "q3": "哈希计数"}},  # q1 答错
        headers=hd,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["score"] == 67 and body["correct_count"] == 2
    assert body["wrong_ids"] == ["q1"]

    wb = (await client.get("/api/v1/quiz/wrongbook", headers=hd)).json()
    assert len(wb["items"]) == 1
    item = wb["items"][0]
    assert item["qid"] == "q1" and item["task_id"] == data["task_id"]
    assert item["direction"] == "Python 后端"
    assert item["answer"] == 1 and "哈希表" in item["analysis"]
    assert len(item["options"]) == 4


async def test_owner_isolation(client):
    """会话 B 看不到 A 的刷题会话：GET exists=False、DELETE 404、列表不可见。"""
    hd_a, hd_b = _sid(), _sid()
    data = await _generate(client, hd_a)
    task_id = data["task_id"]

    got = await client.get(f"/api/v1/quiz/{task_id}", headers=hd_b)
    assert got.status_code == 200 and got.json() == {"exists": False}

    sessions_b = (await client.get("/api/v1/quiz/sessions", headers=hd_b)).json()
    assert all(s["task_id"] != task_id for s in sessions_b)

    resp = await client.delete(f"/api/v1/quiz/sessions/{task_id}", headers=hd_b)
    assert resp.status_code == 404

    # 提交他人会话同样 404；A 自己不受影响
    sub = await client.post(
        f"/api/v1/quiz/{task_id}/submit", json={"answers": {"q1": 1}}, headers=hd_b
    )
    assert sub.status_code == 404
    assert (await client.get(f"/api/v1/quiz/{task_id}", headers=hd_a)).json()["exists"] is True


async def test_double_submit_and_missing_session(client):
    """重复交卷 400；不存在会话 GET 200 {exists: False}。"""
    hd = _sid()
    data = await _generate(client, hd)
    task_id = data["task_id"]
    first = await client.post(
        f"/api/v1/quiz/{task_id}/submit", json={"answers": {"q1": 1, "q2": 1, "q3": "x"}}, headers=hd
    )
    assert first.status_code == 200
    again = await client.post(
        f"/api/v1/quiz/{task_id}/submit", json={"answers": {"q1": 1, "q2": 1, "q3": "x"}}, headers=hd
    )
    assert again.status_code == 400

    missing = await client.get("/api/v1/quiz/qz-notexist00", headers=hd)
    assert missing.status_code == 200 and missing.json() == {"exists": False}


async def test_code_judge_llm_failure_degrades_per_question(client, monkeypatch):
    """编程题 AI 判定失败：单题 correct=None + 自评提示，整体 200 且落 finished。"""
    import app.api.v1.quiz as qm

    async def _gen_ok_judge_boom(prompt, model_cls, **kwargs):
        if model_cls is QuizPlan:
            return QuizPlan.model_validate({"questions": _fake_questions()})
        raise RuntimeError("judge unavailable")

    monkeypatch.setattr(qm, "call_llm_for_json", _gen_ok_judge_boom)
    hd = _sid()
    data = await _generate(client, hd)
    resp = await client.post(
        f"/api/v1/quiz/{data['task_id']}/submit",
        json={"answers": {"q1": 1, "q2": 1, "q3": "哈希计数"}},
        headers=hd,
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    by_qid = {r["qid"]: r for r in body["results"]}
    assert by_qid["q3"]["correct"] is None
    assert "AI 判定不可用" in by_qid["q3"]["comment"]
    assert by_qid["q1"]["correct"] is True
    # None 不计正确也不计错：2/3 → 67，wrong_ids 不含 q3
    assert body["score"] == 67 and body["correct_count"] == 2 and body["wrong_ids"] == []

    got = (await client.get(f"/api/v1/quiz/{data['task_id']}", headers=hd)).json()
    assert got["status"] == "finished"
    row = next(a for a in got["answers"] if a["qid"] == "q3")
    assert row["correct"] is None


async def test_generate_llm_failure_502(client, monkeypatch):
    """出题 LLM 失败 → 502（不静默降级），且不留半成品会话。"""
    hd = _sid()

    async def _boom(*args, **kwargs):
        raise RuntimeError("llm unavailable")

    monkeypatch.setattr(quiz_mod, "call_llm_for_json", _boom)
    resp = await client.post(
        "/api/v1/quiz/generate", json={"direction": "数据分析"}, headers=hd
    )
    assert resp.status_code == 502
    assert "出题失败" in resp.json()["detail"]
    assert (await client.get("/api/v1/quiz/sessions", headers=hd)).json() == []
