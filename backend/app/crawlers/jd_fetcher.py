from loguru import logger
from playwright.async_api import async_playwright


async def fetch_jd_from_url(url: str) -> str:
    """
    从 URL 抓取 JD 文本（通用版，适配常见招聘网站）

    返回：JD 纯文本；失败抛异常
    """
    logger.info(f"尝试抓取 JD: {url}")

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=20000)
            await page.wait_for_timeout(3000)

            # 尝试多种选择器
            selectors = [
                ".job-detail",           # 智联
                ".job-sec",              # BOSS
                ".job-detail-section",   # 51job
                ".job-description",
                "[class*='job-detail']",
                "[class*='job-content']",
                "article",
                "main",
                "body",
            ]

            text = ""
            for sel in selectors:
                try:
                    loc = page.locator(sel).first
                    if await loc.count() > 0:
                        t = await loc.inner_text(timeout=3000)
                        if t and len(t) > 100:
                            text = t
                            logger.info(f"用选择器 {sel} 抓到 {len(t)} 字")
                            break
                except Exception:
                    continue

            if not text:
                raise RuntimeError("页面上找不到 JD 内容")

            # 清理
            text = text.strip()
            text = "\n".join(line.strip() for line in text.split("\n") if line.strip())

            if len(text) < 50:
                raise RuntimeError("抓到的内容太短，可能不是 JD 页面")

            return text

        finally:
            await browser.close()