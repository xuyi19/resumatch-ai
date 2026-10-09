"""M31 独立面试测试：/interview/start-free + /interview/sessions + 独立会话上下文复用。

LLM 调用统一 monkeypatch（不真实调用模型）；重点验证：
- start-free 创建 iv- 前缀会话，上下文存 Conversation.context
- M32 多轮自由对话 /interview/chat：advance 推进、chat_log 落库、末题总评
- sessions 列表返回 source 区分
"""

import json

import pytest
from httpx import ASGITransport, AsyncClient

from app.api.v1.interview import (
    ChatTurn,
    InterviewPlan,
    InterviewQuestion,
    InterviewSummary,
)
from app.main import app

RESUME_TEXT = (
    "张三，本科毕业于某大学计算机专业。技能：Python、FastAPI、MySQL、Redis、Docker。"
    "项目一：电商后台管理系统，负责订单模块与支付对接，QPS 峰值 3000。"
    "项目二：日志采集平台，使用 Kafka 与 ClickHouse，日处理 2 亿条。"
    "工作经历：某科技公司后端工程师两年，主导服务拆分与性能优化，接口平均耗时下降 60%。"
)

JD_TEXT = "岗位职责：负责高并发后端服务设计与开发，参与系统架构演进。任职要求：熟悉 Python/FastAPI，有分布式系统经验。"


def _fake_plan() -> dict:
    return {
        "questions": [
            {"id": f"q{i}", "category": "技术基础", "question": f"第{i}题：Redis 缓存三件套？",
             "focus": "原理深度", "hint": "分点作答"}
            for i in range(1, 7)
        ]
    }


async def _fake_call_llm(prompt, model_cls, **kwargs):
    if model_cls is InterviewPlan:
        return InterviewPlan.model_validate(_fake_plan())
    if model_cls is ChatTurn:
        # 强制收尾标注【强制收尾】（「结束本题」按钮）必须 advance=true，
        # 否则留在本题继续追问；CHAT_PROMPT 正文固定文案不带【】不会误判
        return ChatTurn(reply="好的，这个点先聊到这里", advance="【强制收尾】" in prompt)
    if model_cls is InterviewSummary:
        return InterviewSummary(
            overall="整体表现良好，与岗位匹配度较高",
            # M34 评分量化：fake 与真实 LLM 输出结构保持一致
            overall_score=7.5,
            scores={q["id"]: 7.5 for q in _fake_plan()["questions"]},
            strengths=["基础扎实"], weaknesses=["量化不足"], suggestions=["多用数字"],
        )
    raise AssertionError(f"未预期的模型类型 {model_cls}")


@pytest.fixture
async def client(monkeypatch):
    monkeypatch.setattr("app.api.v1.interview.call_llm_for_json", _fake_call_llm)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


async def _upload_resume(client) -> int:
    res = await client.post(
        "/api/v1/resumes/upload-text",
        json={"filename": "张三-独立面试测试.txt", "text": RESUME_TEXT},
    )
    assert res.status_code == 200, res.text
    return res.json()["id"]


async def test_start_free_creates_session_and_plan(client):
    resume_id = await _upload_resume(client)
    res = await client.post(
        "/api/v1/interview/start-free",
        json={"resume_id": resume_id, "jd_text": JD_TEXT},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["task_id"].startswith("iv-")
    assert len(data["questions"]) == 6
    assert data["status"] == "ongoing"
    assert data["current_index"] == 0

    # 会话列表可查到，source 为独立面试
    res = await client.get("/api/v1/interview/sessions")
    assert res.status_code == 200
    items = res.json()["items"]
    hit = next(x for x in items if x["task_id"] == data["task_id"])
    assert hit["source"] == "独立面试"
    assert hit["total"] == 6 and hit["answered"] == 0

    # GET 恢复会话：题单 + 合成对话流（首题题干，等待候选人发言）
    res = await client.get(f"/api/v1/interview/{data['task_id']}")
    assert res.status_code == 200 and res.json()["exists"] is True
    body = res.json()
    assert len(body["questions"]) == 6
    assert body["chat_log"] == [
        {"role": "interviewer", "qid": "q1", "content": body["questions"][0]["question"]}
    ]


async def test_start_free_with_null_llm_config(client):
    """回归：前端未配置 Key 时显式传 llm_config=null，不应 422（M31 修复）。"""
    resume_id = await _upload_resume(client)
    res = await client.post(
        "/api/v1/interview/start-free",
        json={"resume_id": resume_id, "jd_text": JD_TEXT, "llm_config": None},
    )
    assert res.status_code == 200, res.text
    assert res.json()["task_id"].startswith("iv-")


async def test_start_free_validates_resume_and_jd(client):
    # JD 太短 → 422
    resume_id = await _upload_resume(client)
    res = await client.post(
        "/api/v1/interview/start-free",
        json={"resume_id": resume_id, "jd_text": "太短"},
    )
    assert res.status_code == 422

    # 简历不存在 → 404
    res = await client.post(
        "/api/v1/interview/start-free",
        json={"resume_id": 999999, "jd_text": JD_TEXT},
    )
    assert res.status_code == 404


async def test_chat_multi_round_full_flow(client):
    """M32 多轮自由对话：追问留在本题（advance=false）→ 结束本题推进 → 答完出总评。"""
    resume_id = await _upload_resume(client)
    start = await client.post(
        "/api/v1/interview/start-free",
        json={"resume_id": resume_id, "jd_text": JD_TEXT},
    )
    task_id = start.json()["task_id"]

    # 第 1 题第 1 轮：LLM 判断还需追问 → current_index 不动，chat_log 追加 2 条
    res = await client.post(
        f"/api/v1/interview/chat/{task_id}",
        json={"content": "缓存穿透是恶意请求打不存在的 key，我用布隆过滤器拦截。"},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["advance"] is False
    assert data["next_index"] == 0
    assert data["finished"] is False
    # 初始 1 条题干 + candidate + interviewer 回应
    assert len(data["chat_log"]) == 3
    assert data["chat_log"][-2]["role"] == "candidate"
    assert data["chat_log"][-1]["role"] == "interviewer"

    # 第 1 题第 2 轮：强制收尾 → 推进到 q2；占位文案不落入对话流（只 +收尾回应 +q2 题干）
    res = await client.post(
        f"/api/v1/interview/chat/{task_id}",
        json={"content": "另外还会设置空值缓存并调短过期时间。", "force_advance": True},
    )
    assert res.status_code == 200, res.text
    data = res.json()
    assert data["advance"] is True
    assert data["next_index"] == 1
    assert len(data["chat_log"]) == 5
    assert data["chat_log"][-1]["qid"] == "q2"
    assert data["chat_log"][-1]["role"] == "interviewer"
    assert all("本题回答完毕" not in m["content"] for m in data["chat_log"])

    # chat_log 落库一致（GET 与回包相同）
    res = await client.get(f"/api/v1/interview/{task_id}")
    body = res.json()
    assert body["chat_log"] == data["chat_log"]

    # 剩余 5 题各一轮强制收尾 → 全部答完出总评
    for _ in range(5):
        res = await client.post(
            f"/api/v1/interview/chat/{task_id}",
            json={"content": "分点作答完毕。", "force_advance": True},
        )
        assert res.status_code == 200, res.text
    assert data["finished"] is False  # data 是 q2 推进轮回包，未结束

    # 条数：3（q1 两轮）+ 4×2（q2..q5 强制收尾各 +回应 +题干）+ 1（q6 末题收尾）= 14
    res = await client.get(f"/api/v1/interview/{task_id}")
    body = res.json()
    assert body["status"] == "finished"
    assert body["summary"]["overall"]
    # M34 评分量化：总分与每题得分随总评返回
    assert body["summary"]["overall_score"] == 7.5
    assert body["summary"]["scores"]["q1"] == 7.5
    assert len(body["chat_log"]) == 14
    assert all("本题回答完毕" not in m["content"] for m in body["chat_log"])

    # 已结束的会话再发言 → 400
    res = await client.post(
        f"/api/v1/interview/chat/{task_id}", json={"content": "再聊一句"}
    )
    assert res.status_code == 400


async def test_chat_validates_empty_and_missing_plan(client):
    """无会话/无题单 → 404/400；空内容 → 422。"""
    resume_id = await _upload_resume(client)
    # 会话不存在
    res = await client.post("/api/v1/interview/chat/iv-notexist", json={"content": "你好"})
    assert res.status_code == 404

    start = await client.post(
        "/api/v1/interview/start-free",
        json={"resume_id": resume_id, "jd_text": JD_TEXT},
    )
    task_id = start.json()["task_id"]

    res = await client.post(f"/api/v1/interview/chat/{task_id}", json={"content": ""})
    assert res.status_code == 422


async def test_start_free_reuses_existing_plan(client):
    """重复点击开始同一场景：start 幂等——已有题单不重复生成（消耗不翻倍）。"""
    resume_id = await _upload_resume(client)
    free = await client.post(
        "/api/v1/interview/start-free",
        json={"resume_id": resume_id, "jd_text": JD_TEXT},
    )
    task_id = free.json()["task_id"]
    # 再次走 start/{task_id}（面板首次加载路径）→ 不重建、不换 id
    res = await client.post(f"/api/v1/interview/start/{task_id}", json={})
    assert res.status_code == 200
    assert len(res.json()["questions"]) == 6


async def test_export_interview_report(client):
    """M33 面试报告导出：未完成 409 / 不存在 404 / 完成后 blob（docx 魔数）。"""
    resume_id = await _upload_resume(client)
    start = await client.post(
        "/api/v1/interview/start-free",
        json={"resume_id": resume_id, "jd_text": JD_TEXT},
    )
    task_id = start.json()["task_id"]

    # 未完成（无总评）→ 409
    res = await client.post(f"/api/v1/interview/export/{task_id}")
    assert res.status_code == 409

    # 走完全部题目（模拟真实节奏：先真实发言入对话流，再强制收尾推进；
    # fake LLM 见【强制收尾】必 advance，占位控制语不入 chat_log）
    for _ in range(6):
        r = await client.post(
            f"/api/v1/interview/chat/{task_id}",
            json={"content": "分点作答，结合项目经验展开。"},
        )
        assert r.status_code == 200, r.text
        r = await client.post(
            f"/api/v1/interview/chat/{task_id}",
            json={"content": "（本题回答完毕，请进入下一题）", "force_advance": True},
        )
        assert r.status_code == 200, r.text

    res = await client.post(f"/api/v1/interview/export/{task_id}")
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith(
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document")
    assert res.content[:2] == b"PK"  # docx = zip 容器魔数

    # M47 附录：多轮对话全文进入报告正文（题干 = 面试官 / 回答 = 我）
    import io as _io
    from docx import Document as _Doc

    doc = _Doc(_io.BytesIO(res.content))
    texts = [p.text for p in doc.paragraphs]
    assert any("附录 · 多轮对话全文" in t for t in texts)
    assert any(t.startswith("面试官：") for t in texts)
    assert any(t.startswith("我：") for t in texts)

    # 会话不存在 → 404
    res = await client.post("/api/v1/interview/export/iv-notexist")
    assert res.status_code == 404


# ---------------- 优化⑩ 流式 SSE /chat-stream ----------------

class _FakeStreamLLM:
    """按预设 token 片段流式输出（模拟 langchain astream 的 AIMessageChunk）。"""

    def __init__(self, pieces):
        self._pieces = pieces

    async def astream(self, _prompt):
        for p in self._pieces:
            yield type("Chunk", (), {"content": p})()


def _sse_events(text: str) -> list[dict]:
    """解析 SSE 文本为事件列表（取每个块的 data: 行 JSON；fatal 块带 _fatal 标记）。"""
    events = []
    for block in text.split("\n\n"):
        data_line = next(
            (l for l in block.split("\n") if l.startswith("data:")), None
        )
        if data_line is None:
            continue
        payload = json.loads(data_line[5:].strip())
        if block.startswith("event: fatal"):
            payload["_fatal"] = True
        events.append(payload)
    return events


async def _start_free(client) -> str:
    resume_id = await _upload_resume(client)
    res = await client.post(
        "/api/v1/interview/start-free",
        json={"resume_id": resume_id, "jd_text": JD_TEXT},
    )
    assert res.status_code == 200, res.text
    return res.json()["task_id"]


async def test_chat_stream_sse_flow(client, monkeypatch):
    """流式端点：delta 增量可拼接为 reply；final 与 /chat 回包结构一致；落库一致。"""
    task_id = await _start_free(client)
    pieces = ['{"', 'reply', '": "', '好的，', '布隆过滤器是关键。', '", ', '"advance": false}']
    monkeypatch.setattr(
        "app.api.v1.interview.get_llm", lambda **kwargs: _FakeStreamLLM(pieces)
    )

    res = await client.post(
        f"/api/v1/interview/chat-stream/{task_id}",
        json={"content": "缓存穿透我用布隆过滤器拦截。"},
    )
    assert res.status_code == 200, res.text
    assert res.headers["content-type"].startswith("text/event-stream")

    events = _sse_events(res.text)
    assert not any(e.get("_fatal") for e in events)
    assert events[0]["type"] == "start"
    deltas = "".join(e["text"] for e in events if e["type"] == "delta")
    assert deltas == "好的，布隆过滤器是关键。"

    final = events[-1]
    assert final["type"] == "final"
    assert final["reply"] == "好的，布隆过滤器是关键。"
    assert final["advance"] is False
    assert final["finished"] is False
    assert final["next_index"] == 0
    assert final["total"] == 6
    # 初始 1 条题干 + candidate + interviewer 回应
    assert len(final["chat_log"]) == 3
    assert final["chat_log"][-2]["role"] == "candidate"
    assert final["chat_log"][-1]["role"] == "interviewer"

    # 落库一致：GET 会话回包与 final 相同
    res = await client.get(f"/api/v1/interview/{task_id}")
    assert res.json()["chat_log"] == final["chat_log"]


async def test_chat_stream_force_advance_and_summary(client, monkeypatch):
    """强制收尾推进（advance=true 占位文案不入对话流）→ 末题收尾发 stage + 总评。"""
    task_id = await _start_free(client)
    monkeypatch.setattr(
        "app.api.v1.interview.get_llm",
        lambda **kwargs: _FakeStreamLLM(['{"reply": "答得不错", "advance": true}']),
    )

    # q1 强制收尾 → 推进 q2
    res = await client.post(
        f"/api/v1/interview/chat-stream/{task_id}",
        json={"content": "（本题回答完毕，请进入下一题）", "force_advance": True},
    )
    events = _sse_events(res.text)
    final = events[-1]
    assert final["advance"] is True
    assert final["next_index"] == 1
    assert final["chat_log"][-1]["qid"] == "q2"
    assert all("本题回答完毕" not in m["content"] for m in final["chat_log"])

    # q2..q5 各强制收尾一轮
    for _ in range(4):
        res = await client.post(
            f"/api/v1/interview/chat-stream/{task_id}",
            json={"content": "分点作答完毕。", "force_advance": True},
        )
        assert res.status_code == 200, res.text

    # q6 末题收尾：stage=summarizing → final 带 summary，状态落库为 finished
    res = await client.post(
        f"/api/v1/interview/chat-stream/{task_id}",
        json={"content": "最后一题答完。", "force_advance": True},
    )
    events = _sse_events(res.text)
    assert [e["stage"] for e in events if e["type"] == "stage"] == ["summarizing"]
    final = events[-1]
    assert final["finished"] is True
    assert final["summary"]["overall_score"] == 7.5
    assert final["summary"]["scores"]["q1"] == 7.5

    res = await client.get(f"/api/v1/interview/{task_id}")
    body = res.json()
    assert body["status"] == "finished"
    assert body["summary"]["overall"]


async def test_chat_stream_invalid_json_keeps_streamed_reply(client, monkeypatch):
    """流式输出 JSON 结构中断（如缺右括号）：已流出的发言保留，advance 安全降级 false。"""
    task_id = await _start_free(client)
    # 缺收尾 }：整体 JSON 解析失败，但 reply 字符串值已完整流出（可边收边显）
    monkeypatch.setattr(
        "app.api.v1.interview.get_llm",
        lambda **kwargs: _FakeStreamLLM(
            ['{"reply": "我想说：缓存穿透用布隆过滤器拦截', '", ', '"advance": true']
        ),
    )

    res = await client.post(
        f"/api/v1/interview/chat-stream/{task_id}", json={"content": "请点评"}
    )
    assert res.status_code == 200, res.text
    events = _sse_events(res.text)
    assert not any(e.get("_fatal") for e in events)
    final = events[-1]
    assert final["reply"] == "我想说：缓存穿透用布隆过滤器拦截"
    assert final["advance"] is False
    assert final["next_index"] == 0


async def test_chat_stream_fallback_on_stream_error(client, monkeypatch):
    """astream 中途抛错 → 自动降级非流式 call_llm_for_json，未流出部分一次性补发。"""
    task_id = await _start_free(client)

    class _BoomLLM:
        async def astream(self, _prompt):
            yield type("Chunk", (), {"content": '{"reply"'})()
            raise RuntimeError("连接中断")

    monkeypatch.setattr("app.api.v1.interview.get_llm", lambda **kwargs: _BoomLLM())

    res = await client.post(
        f"/api/v1/interview/chat-stream/{task_id}", json={"content": "你好"}
    )
    assert res.status_code == 200, res.text
    events = _sse_events(res.text)
    assert not any(e.get("_fatal") for e in events)
    final = events[-1]
    # 降级后取 fake call_llm_for_json 的回应；delta 把未流出部分一次性补齐
    assert final["reply"] == "好的，这个点先聊到这里"
    assert "".join(e.get("text", "") for e in events if e["type"] == "delta") == \
        "好的，这个点先聊到这里"


async def test_chat_stream_validates_before_stream(client):
    """会话不存在：开流前 404（普通 HTTP 错误，而非 SSE fatal）。"""
    res = await client.post(
        "/api/v1/interview/chat-stream/iv-notexist", json={"content": "你好"}
    )
    assert res.status_code == 404
