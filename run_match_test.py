import os
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"

import asyncio

from app.matching.semantic_matcher import _get_model  # ★ 先加载模型
from app.core.db import AsyncSessionLocal
from app.services.match_service import MatchService


SAMPLE_RESUME = """
个人简历

姓名：张三
学历：本科
工作年限：3年

技能：Python, FastAPI, Django, MySQL, Redis, Docker, Linux, Git

工作经历：
2021.07 - 2024.07  某互联网公司  后端开发工程师
- 负责核心业务系统后端开发，使用 Python + FastAPI 搭建微服务
- 优化数据库查询，引入 Redis 缓存，接口响应时间降低 60%
- 参与爬虫系统开发，抓取百万级数据并清洗入库

项目经验：
- 智能招聘系统：基于 LangChain 实现简历解析和岗位匹配
"""


async def main():
    # ★ 先在数据库 session 打开之前把模型加载好
    print("预热语义模型...")
    _get_model()
    print("模型已就绪，开始匹配\n")

    async with AsyncSessionLocal() as session:
        service = MatchService(session)
        results = await service.recommend(SAMPLE_RESUME, top_k=10,
                                          use_semantic=True)
        print("========== Top 10 匹配结果 ==========\n")
        for i, r in enumerate(results, 1):
            print(f"[{i}] {r['score']}分  {r['title']} @ {r['company']} ({r['city']})")
            print(f"    匹配技能: {', '.join(r['matched_skills'][:8])}")
            print(f"    缺失技能: {', '.join(r['missing_skills'][:8])}")
            print(f"    分项: {r['breakdown']}\n")


if __name__ == "__main__":
    asyncio.run(main())