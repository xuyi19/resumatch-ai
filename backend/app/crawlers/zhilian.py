import hashlib
import re
from urllib.parse import quote

from loguru import logger
from playwright.async_api import async_playwright
from tenacity import retry, stop_after_attempt, wait_exponential

from app.crawlers.base import BaseJobCrawler


class ZhilianCrawler(BaseJobCrawler):
    """智联招聘爬虫（翻页版）"""

    BASE_URL = "https://www.zhaopin.com/jobs"
    CITY_MAP = {"北京": "530", "上海": "538", "深圳": "765", "广州": "763", "杭州": "653"}

    EDU_SET = {"大专", "本科", "硕士", "博士", "中专", "高中", "不限", "学历不限"}
    EXP_PATTERN = re.compile(r"^(\d+[-~]\d+年|\d+年以上|经验不限|应届|在校/应届)$")

    def __init__(self, headless: bool = True):
        self.headless = headless

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=3, max=10))
    async def fetch_job_list(
        self, keyword: str, city: str = "北京", max_pages: int = 5
    ) -> list[dict]:
        """
        :param keyword: 搜索关键词
        :param city: 城市名
        :param max_pages: 最多翻几页，每页 20 条
        """
        city_code = self.CITY_MAP.get(city, "530")
        all_jobs: list[dict] = []
        seen_ids: set[str] = set()

        async with async_playwright() as p:
            browser = await p.chromium.launch(
                headless=self.headless,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = await browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1440, "height": 900},
            )
            page = await context.new_page()

            for page_num in range(1, max_pages + 1):
                url = f"{self.BASE_URL}?jl={city_code}&kw={quote(keyword)}&p={page_num}"
                logger.info(f"打开第 {page_num} 页: {url}")

                try:
                    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    await page.wait_for_selector(".job-card", timeout=15000)
                    await page.wait_for_timeout(2000)
                except Exception as e:
                    logger.warning(f"第 {page_num} 页加载失败: {e}")
                    break

                cards = await page.locator(".job-card").all()
                logger.info(f"第 {page_num} 页找到 {len(cards)} 个卡片")

                if not cards:
                    logger.info(f"第 {page_num} 页无数据，停止翻页")
                    break

                # 判断这一页是不是和上一页重复（智联有时超页会返回第一页）
                page_ids = set()
                for card in cards:
                    try:
                        job = await self._parse_card(card, city)
                    except Exception as e:
                        logger.debug(f"解析卡片失败: {e}")
                        continue
                    if not job or not job.get("title"):
                        continue
                    page_ids.add(job["source_id"])
                    if job["source_id"] in seen_ids:
                        continue
                    seen_ids.add(job["source_id"])
                    all_jobs.append(job)

                # 如果这一页全是重复的，说明翻页到底了
                if not page_ids - seen_ids and page_num > 1:
                    logger.info("本页数据全部重复，停止翻页")
                    break

                await page.wait_for_timeout(1500)

            await browser.close()

        logger.info(f"去重后共 {len(all_jobs)} 条职位")
        return all_jobs

    async def _parse_card(self, card, city: str) -> dict | None:
        text = (await card.inner_text()).strip()
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if len(lines) < 3:
            return None

        title = await self._safe_text(card, ".job-card__title-main") or lines[0]
        company = await self._safe_text(card, ".job-card__company-name") or ""
        location = await self._safe_text(card, ".job-card__location") or ""

        salary = education = experience = None
        tags: list[str] = []

        for line in lines[1:]:
            if line in (title, company, location):
                continue
            if salary is None and ("元" in line or "薪" in line):
                salary = line
                continue
            if education is None and line in self.EDU_SET:
                education = line
                continue
            if experience is None and self.EXP_PATTERN.match(line):
                experience = line
                continue
            tags.append(line)

        key = f"{title}|{company}|{location}"
        source_id = "zl_" + hashlib.md5(key.encode("utf-8")).hexdigest()[:16]

        return {
            "source": "zhilian",
            "source_id": source_id,
            "title": title,
            "company": company,
            "city": city,
            "salary": salary,
            "experience": experience,
            "education": education,
            "tags": tags,
            "description": text,
        }

    @staticmethod
    async def _safe_text(card, selector: str) -> str | None:
        try:
            loc = card.locator(selector).first
            if await loc.count() == 0:
                return None
            return (await loc.inner_text()).strip()
        except Exception:
            return None

    async def fetch_job_detail(self, job_id: str) -> dict:
        return {}