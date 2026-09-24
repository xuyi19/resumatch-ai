# -*- coding: utf-8 -*-
"""M29 补充：AI 岗位画像数据源（解析/降级）+ 任务放弃释放名额。"""
import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.main import app
from app.services.job_market import AIJobProvider, JobProviderError, create_provider


def test_ai_provider_parse_valid():
    """LLM 返回合法 JSON 数组 → 归一化 JobItem（source=AI 参考岗位）"""
    content = '''```json
[
  {"title": "Java 后端工程师", "company": "某电商", "salary": "20-35K·14薪",
   "city": "杭州", "jd": "负责订单/支付/库存系统研发，熟悉 Spring Cloud、MySQL、Redis。"},
  {"title": "", "company": "无效行应被跳过", "salary": "", "city": "", "jd": ""}
]
```'''
    items = AIJobProvider()._parse(content)
    assert len(items) == 1
    assert items[0].source == "AI 参考岗位"
    assert items[0].id == "ai-1"
    assert "订单" in items[0].jd_text


def test_ai_provider_parse_invalid_raises():
    """非 JSON 输出 → JobProviderError（前端按 unknown 归因提示）"""
    with pytest.raises(JobProviderError):
        AIJobProvider()._parse("抱歉，我无法生成")


def test_create_provider_ai_has_llm_config():
    """工厂：ai → AIJobProvider 且 llm_config 透传；未知 id 回退 mock"""
    p = create_provider("ai", llm_config={"api_key": "k", "model": "m"})
    assert p.name == "ai"
    assert p.llm_config.get("model") == "m"
    assert create_provider("whatever").name == "mock"


@pytest.mark.asyncio
async def test_abandon_release_and_404():
    """放弃未完成任务：DB 状态转 failed；再次放弃 404（已终态）"""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 造一份简历并启动任务（mock LLM 不可达也没关系，任务立即处于 pending/running）
        r = await client.post("/api/v1/resumes/upload-text", json={
            "filename": "放弃测试.txt",
            "text": "姓名：李四\\n学历：本科\\n技能：Python / FastAPI / SQL，" * 4,
        })
        resume_id = r.json()["id"]
        r = await client.post("/api/v1/live/analyze", json={
            "resume_id": resume_id,
            "jd_text": "招聘高级 Java 后端工程师，负责电商核心系统设计与开发，要求熟悉 Spring 全家桶。",
        })
        assert r.status_code == 200
        task_id = r.json()["task_id"]

        # 放弃 → 成功；再放弃 → 404（已终态）
        r = await client.post(f"/api/v1/live/abandon/{task_id}")
        assert r.status_code == 200
        assert r.json()["status"] == "failed"
        r = await client.post(f"/api/v1/live/abandon/{task_id}")
        assert r.status_code == 404

        # 状态接口确认 failed（内存或 DB 快照）
        r = await client.get(f"/api/v1/live/status/{task_id}")
        assert r.status_code == 200
        assert r.json()["status"] in ("failed", "success")  # LLM 若秒完成取 success
