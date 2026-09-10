import asyncio

from loguru import logger

from app.crawlers.pipeline import JobPipeline
from app.crawlers.zhilian import ZhilianCrawler


async def main():
    crawler = ZhilianCrawler(headless=False)
    pipeline = JobPipeline()

    keywords = [
        "python开发",
        "后端开发",
        "数据分析",
        "大模型",
        "算法工程师",
        "Java开发",
        "前端开发",
        "运维工程师",
    ]
    total = 0
    for kw in keywords:
        logger.info(f"===== 开始抓取: {kw} =====")
        jobs = await crawler.fetch_job_list(keyword=kw, city="北京", max_pages=1)
        logger.info(f"{kw} 抓到 {len(jobs)} 条")
        await pipeline.process(jobs)
        total += len(jobs)
        await asyncio.sleep(3)   # 关键词之间间隔，避免反爬

    logger.info(f"全部完成，共抓取 {total} 条")


if __name__ == "__main__":
    asyncio.run(main())