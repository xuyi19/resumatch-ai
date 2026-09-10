import hashlib
import re
from urllib.parse import quote

from loguru import logger
from playwright.sync_api import sync_playwright


class ZhilianCrawlerSync:
    """智联招聘爬虫 —— 同步版（运行在独立线程，避免与 uvicorn 事件循环冲突）"""

    BASE_URL = "https://www.zhaopin.com/jobs"
    CITY_MAP = {"北京": "530", "上海": "538", "深圳": "765", "广州": "763", "杭州": "653"}
    EDU_SET = {"大专", "本科", "硕士", "博士", "中专", "高中", "不限", "学历不限"}
    EXP_PATTERN = re.compile(r"^(\d+[-~]\d+年|\d+年以上|经验不限|应届|在校/应届)$")

    def fetch_job_list(self, keyword: str, city: str = "北京", max_pages: int = 2) -> list[dict]:
        city_code = self.CITY_MAP.get(city, "530")
        all_jobs: list[dict] = []
        seen_ids: set[str] = set()

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=["--disable-blink-features=AutomationControlled"],
            )
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1440, "height": 900},
            )
            page = context.new_page()

            for page_num in range(1, max_pages + 1):
                url = f"{self.BASE_URL}?jl={city_code}&kw={quote(keyword)}&p={page_num}"
                logger.info(f"[sync] 打开第 {page_num} 页: {url}")

                try:
                    page.goto(url, wait_until="domcontentloaded", timeout=30000)
                    page.wait_for_selector(".job-card", timeout=15000)
                    page.wait_for_timeout(2000)
                except Exception as e:
                    logger.warning(f"[sync] 第 {page_num} 页加载失败: {e}")
                    break

                cards = page.locator(".job-card").all()
                logger.info(f"[sync] 第 {page_num} 页找到 {len(cards)} 个卡片")

                if not cards:
                    break

                page_ids: set[str] = set()
                for card in cards:
                    try:
                        job = self._parse_card(card, city)
                    except Exception as e:
                        logger.debug(f"[sync] 解析失败: {e}")
                        continue
                    if not job or not job.get("title"):
                        continue
                    page_ids.add(job["source_id"])
                    if job["source_id"] in seen_ids:
                        continue
                    seen_ids.add(job["source_id"])
                    all_jobs.append(job)

                # 整页都是旧的，说明翻到底了
                if not page_ids - seen_ids and page_num > 1:
                    break

                page.wait_for_timeout(1500)

            browser.close()

        logger.info(f"[sync] 去重后共 {len(all_jobs)} 条职位")
        return all_jobs

    def _parse_card(self, card, city: str) -> dict | None:
        text = card.inner_text().strip()
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        if len(lines) < 3:
            return None

        title = self._safe_text(card, ".job-card__title-main") or lines[0]
        company = self._safe_text(card, ".job-card__company-name") or ""
        location = self._safe_text(card, ".job-card__location") or ""

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
    def _safe_text(card, selector: str):
        try:
            loc = card.locator(selector).first
            if loc.count() == 0:
                return None
            return loc.inner_text().strip()
        except Exception:
            return None