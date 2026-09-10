import asyncio
import json

from httpx import ASGITransport, AsyncClient

from app.main import app


async def main():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test",
                           timeout=180.0) as client:
        # 用之前上传的简历 id=1
        print("调用 /api/v1/match/with-diagnosis（resume_id=1，top_k=5）...")
        print("预计等待 40-90 秒...\n")

        payload = {
            "resume_id": 1,
            "top_k": 5,
            "diagnose_job_id": None,       # 默认诊断 Top1
            "skip_diagnosis": False,
        }

        r = await client.post("/api/v1/match/with-diagnosis", json=payload)
        print(f"状态码: {r.status_code}\n")

        if r.status_code != 200:
            print("错误:", r.text)
            return

        data = r.json()

        # 打印 Top-N
        print("=" * 60)
        print(f"Top {len(data['top_jobs'])} 岗位匹配：")
        print("=" * 60)
        for i, j in enumerate(data["top_jobs"], 1):
            print(f"[{i}] {j['score']}分  {j['title']} @ {j['company']} ({j['city']})")
            print(f"    匹配技能: {', '.join(j['matched_skills'][:8])}")

        # 打印诊断目标
        if data.get("diagnosis_target"):
            t = data["diagnosis_target"]
            print(f"\n诊断目标: {t['title']} @ {t['company']}")

        # 打印诊断报告
        if data.get("diagnosis"):
            d = data["diagnosis"]
            print("\n" + "=" * 60)
            print("多智能体诊断报告")
            print("=" * 60)

            print("\n【评分】")
            for k, v in d.get("scores", {}).items():
                if isinstance(v, dict):
                    print(f"  {k}: {v['score']}  {v.get('comment', '')}")
                else:
                    print(f"  {k}: {v}")

            print("\n【差距分析】")
            for g in d.get("gaps", []):
                if "summary" in g:
                    print(f"  总结: {g['summary']}")
                else:
                    print(f"  [{g.get('severity')}] {g.get('dimension')}: {g.get('description')}")

            print("\n【改写建议】")
            for s in d.get("suggestions", []):
                if "overall_advice" in s:
                    print(f"  整体建议: {s['overall_advice']}")
                else:
                    print(f"  · {s.get('target')}")
                    print(f"    原文: {s.get('original')}")
                    print(f"    改写: {s.get('rewritten')}")
                    print(f"    理由: {s.get('reason')}\n")


if __name__ == "__main__":
    asyncio.run(main())