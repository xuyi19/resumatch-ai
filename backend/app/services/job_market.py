"""M19 岗位市场适配层：JobProvider 数据源模式。

设计要点（论文可写）：
- 只接官方/三方数据 API，不做网页爬虫（合规与稳定性）
- 适配器模式：各厂商实现统一 search 接口，出口统一归一化为 JobItem
- MockProvider 兜底：未配置 Key / 数据源失效 / 离线演示时保证功能可用
- 错误分类归因：invalid_key / quota / network / maintenance / unknown
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass

from loguru import logger

MAX_JD_LEN = 4000


class JobProviderError(Exception):
    """招聘数据源错误，error_type 用于前端归因提示。"""

    def __init__(self, error_type: str, message: str):
        self.error_type = error_type  # invalid_key | quota | network | maintenance | unknown
        super().__init__(message)


@dataclass
class JobItem:
    """归一化岗位条目：所有 Provider 的出口统一结构。"""

    id: str
    title: str
    company: str
    salary: str
    city: str
    source: str
    jd_text: str
    url: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


# ---------------------------------------------------------------- 内置 Provider


class MockProvider:
    """内置示例岗位：未配 Key / 离线演示兜底，样本风格贴近真实 JD。"""

    name = "mock"

    _SAMPLES = [
        {
            "title": "Python 后端开发工程师",
            "company": "云帆科技",
            "salary": "15-25K·14薪",
            "city": "杭州",
            "jd_text": (
                "岗位职责：\n1. 负责公司核心业务系统的后端开发与迭代；\n"
                "2. 参与高并发服务的设计与优化，保障系统稳定性；\n3. 与前端、产品协作完成需求交付。\n\n"
                "任职要求：\n1. 本科及以上学历，计算机相关专业；\n"
                "2. 熟悉 Python/FastAPI，熟悉 MySQL/Redis，了解消息队列；\n"
                "3. 良好的编码习惯与团队协作能力。有 AI 应用开发经验者优先。"
            ),
        },
        {
            "title": "AI 应用开发工程师（LLM 方向）",
            "company": "智启智能",
            "salary": "20-35K·15薪",
            "city": "北京",
            "jd_text": (
                "岗位职责：\n1. 基于大语言模型构建智能应用（RAG、Agent、结构化输出）；\n"
                "2. 负责 Prompt 工程设计与效果调优；\n3. 搭建 LLM 可观测与评测体系。\n\n"
                "任职要求：\n1. 熟悉 LangChain/LangGraph 或同类框架；\n"
                "2. 了解向量检索、embedding、重排等 RAG 技术；\n"
                "3. 熟悉 Python，良好的工程化能力。有简历优化/招聘类产品经验加分。"
            ),
        },
        {
            "title": "前端开发工程师（Vue3）",
            "company": "星河网络",
            "salary": "13-22K",
            "city": "上海",
            "jd_text": (
                "岗位职责：\n1. 负责 B 端/Web 应用的前端开发；\n2. 参与组件库与设计系统建设。\n\n"
                "任职要求：\n1. 熟悉 Vue3/Vite/Pinia，熟悉 TypeScript；\n"
                "2. 了解 TailwindCSS 与响应式布局；\n3. 对交互体验有追求，沟通良好。"
            ),
        },
        {
            "title": "产品经理（AI 产品）",
            "company": "慧点未来",
            "salary": "18-30K",
            "city": "深圳",
            "jd_text": (
                "岗位职责：\n1. 负责 AI 类产品从 0 到 1 的规划与落地；\n"
                "2. 撰写 PRD，跟进设计与研发交付；\n3. 分析用户反馈，持续迭代。\n\n"
                "任职要求：\n1. 3 年以上产品经验，有 AI 工具类产品经验优先；\n"
                "2. 逻辑清晰，数据敏感，熟悉竞品分析方法。"
            ),
        },
        {
            "title": "数据分析师",
            "company": "数澜咨询",
            "salary": "12-20K",
            "city": "成都",
            "jd_text": (
                "岗位职责：\n1. 负责业务数据的取数、报表与专题分析；\n"
                "2. 搭建指标体系，输出分析报告支持决策。\n\n"
                "任职要求：\n1. 熟悉 SQL，熟练使用 Python/pandas；\n"
                "2. 有 A/B 测试、漏斗分析经验者优先；沟通表达清晰。"
            ),
        },
        {
            "title": "Java 开发工程师",
            "company": "恒信软件",
            "salary": "14-24K·14薪",
            "city": "南京",
            "jd_text": (
                "岗位职责：\n1. 参与企业级 Java 服务开发；\n2. 负责模块设计与代码评审。\n\n"
                "任职要求：\n1. 熟悉 Spring Boot/Spring Cloud；\n"
                "2. 熟悉 MySQL、Redis、Kafka；3. 本科及以上，2 年以上经验。"
            ),
        },
        {
            "title": "运营专员（用户增长）",
            "company": "轻橙互娱",
            "salary": "9-15K",
            "city": "广州",
            "jd_text": (
                "岗位职责：\n1. 负责用户增长活动策划与执行；\n2. 维护社群，分析转化数据。\n\n"
                "任职要求：\n1. 1 年以上互联网运营经验；\n2. 数据驱动，执行力强，文案能力好。"
            ),
        },
        {
            "title": "测试开发工程师",
            "company": "卓越质检",
            "salary": "13-21K",
            "city": "武汉",
            "jd_text": (
                "岗位职责：\n1. 负责自动化测试框架搭建与用例维护；\n2. 参与 CI/CD 流程建设。\n\n"
                "任职要求：\n1. 熟悉 Python，了解 Selenium/Playwright；\n"
                "2. 熟悉接口测试与性能测试基础。"
            ),
        },
        {
            "title": "算法工程师（推荐方向）",
            "company": "浪潮数科",
            "salary": "25-40K",
            "city": "北京",
            "jd_text": (
                "岗位职责：\n1. 负责推荐系统召回/排序模型迭代；\n2. 特征工程与离线评测。\n\n"
                "任职要求：\n1. 硕士及以上，熟悉协同过滤/深度学习推荐模型；\n"
                "2. 熟悉 PyTorch，有大规模数据经验优先。"
            ),
        },
        {
            "title": "UI 设计师",
            "company": "未迟创意",
            "salary": "10-18K",
            "city": "杭州",
            "jd_text": (
                "岗位职责：\n1. 负责 Web/移动端界面设计；\n2. 参与设计规范与组件库维护。\n\n"
                "任职要求：\n1. 熟悉 Figma；2. 有 B 端或工具类产品经验优先；审美在线。"
            ),
        },
        {
            "title": "DevOps 工程师",
            "company": "蓝鲸云服",
            "salary": "16-28K",
            "city": "远程",
            "jd_text": (
                "岗位职责：\n1. 负责容器化部署与 K8s 集群运维；\n2. 建设监控告警体系。\n\n"
                "任职要求：\n1. 熟悉 Docker/K8s、Linux；\n2. 了解 Terraform/GitHub Actions。支持远程办公。"
            ),
        },
        {
            "title": "新媒体运营",
            "company": "观澜文化",
            "salary": "8-13K",
            "city": "长沙",
            "jd_text": (
                "岗位职责：\n1. 负责公众号/短视频账号内容策划与发布；\n2. 跟踪热点，产出选题。\n\n"
                "任职要求：\n1. 文案功底好，会剪映/PS 加分；2. 有成功账号运营经验优先。"
            ),
        },
    ]

    def search(self, keyword: str, city: str = "", page: int = 1, page_size: int = 20) -> tuple[list[JobItem], bool]:
        kw = (keyword or "").strip().lower()
        ct = (city or "").strip()

        def hit(j: dict) -> bool:
            if ct and ct not in j["city"]:
                return False
            if not kw:
                return True
            blob = (j["title"] + j["jd_text"]).lower()
            # 中文按 2-gram、英文按词，任一命中即视为匹配
            for tok in _tokenize(kw):
                if tok in blob:
                    return True
            return False

        rows = [j for j in self._SAMPLES if hit(j)]
        fallback = False
        if not rows:
            rows = list(self._SAMPLES)  # 演示兜底：无命中时给出全部示例
            fallback = True

        items = [
            JobItem(
                id=f"mock-{i + 1}",
                title=j["title"],
                company=j["company"],
                salary=j["salary"],
                city=j["city"],
                source="示例数据",
                jd_text=j["jd_text"],
                url="",
            )
            for i, j in enumerate(rows)
        ]
        start = (max(1, page) - 1) * page_size
        return items[start : start + page_size], fallback


class AIJobProvider:
    """AI 岗位画像：用用户已配置的 LLM 按关键词/城市生成典型岗位参考。

    定位：国内在招岗位暂无稳定开放的官方免费 API，
    用 LLM 生成目标岗位的「参考画像」替代——需明确标注非实时在招数据。
    LLM 失败时降级 MockProvider 样例，保证功能不落空。
    """

    name = "ai"
    _SOURCE = "AI 参考岗位"

    def __init__(self, llm_config: dict | None = None):
        self.llm_config = llm_config or {}

    async def search(self, keyword: str, city: str = "", page: int = 1, page_size: int = 10) -> tuple[list[JobItem], bool]:
        from app.agents.llm import get_llm

        kw = (keyword or "").strip()
        ct = (city or "").strip()
        try:
            llm = get_llm(temperature=0.6, **{
                k: v for k, v in self.llm_config.items()
                if k in ("api_key", "base_url", "model")
            })
            prompt = (
                f"你是招聘信息专家。生成 {page_size} 个「{kw or '通用技术岗'}」"
                f"{'（城市：' + ct + '）' if ct else ''}的典型招聘岗位画像，"
                "用于求职参考。要求：贴近中国市场真实薪资（人民币/月）、公司风格多样、"
                "JD 包含岗位职责与任职要求（120-200 字）。"
                "严格输出 JSON 数组，不要任何其他内容：\n"
                '[{"title":"...","company":"...","salary":"...","city":"...","jd":"..."}]'
            )
            resp = await llm.ainvoke(prompt)
            return self._parse(resp.content)[:page_size], False
        except JobProviderError:
            raise
        except Exception as e:
            logger.warning(f"AI 岗位画像生成失败，降级示例数据：{e}")
            return MockProvider().search(keyword, city, page, page_size), True

    def _parse(self, content: str) -> list[JobItem]:
        """解析 LLM 生成的岗位 JSON；空结果抛错归因（上层可提示换数据源）。"""
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", (content or "").strip(), flags=re.S)
        start, end = text.find("["), text.rfind("]")
        if start == -1 or end == -1 or end <= start:
            raise JobProviderError("unknown", "AI 返回格式异常，请重试或更换数据源")
        try:
            rows = json.loads(text[start : end + 1])
        except json.JSONDecodeError as e:
            raise JobProviderError("unknown", f"AI 返回解析失败：{e}") from e
        items = []
        for i, r in enumerate(rows if isinstance(rows, list) else []):
            if not isinstance(r, dict) or not str(r.get("title", "")).strip():
                continue
            items.append(
                JobItem(
                    id=f"ai-{i + 1}",
                    title=str(r.get("title", ""))[:80],
                    company=str(r.get("company", ""))[:60],
                    salary=str(r.get("salary", ""))[:40],
                    city=str(r.get("city", ""))[:20],
                    source=self._SOURCE,
                    jd_text=str(r.get("jd", ""))[:MAX_JD_LEN],
                    url="",
                )
            )
        if not items:
            raise JobProviderError("unknown", "AI 未生成有效岗位，请重试或更换数据源")
        return items


# ---------------------------------------------------------------- 工厂与工具

PROVIDER_IDS = ("mock", "ai")


def create_provider(provider: str, api_key: str = "", api_id: str = "",
                    llm_config: dict | None = None) -> object:
    """按数据源标识构建 Provider 实例；未知标识回退 Mock（兜底不落空）。

    AI 数据源需要 llm_config（用户已配置的模型）；其余 Provider 忽略该参数。
    """
    p = (provider or "").strip().lower()
    if p == "ai":
        return AIJobProvider(llm_config)
    return MockProvider()


def _tokenize(text: str) -> list[str]:
    """英文按小写词、中文按 2-gram 切分（粗筛特征）。"""
    text = (text or "").lower()
    tokens = re.findall(r"[a-z][a-z0-9+#.]+", text)
    han = re.findall(r"[\u4e00-\u9fa5]", text)
    tokens += [han[i] + han[i + 1] for i in range(len(han) - 1)]
    return sorted(set(tokens))


def jaccard(a: list[str], b: list[str]) -> float:
    sa, sb = set(a), set(b)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / len(sa | sb)


def coarse_rank(resume_text: str, jobs: list[JobItem], keep: int = 30) -> list[tuple[JobItem, float]]:
    """粗筛：简历文本与岗位标题+JD 的 Jaccard 相似度，取 Top keep 条。"""
    res_tokens = _tokenize(resume_text)
    scored = []
    for j in jobs:
        score = jaccard(res_tokens, _tokenize(j.title + " " + j.jd_text))
        scored.append((j, score))
    scored.sort(key=lambda t: t[1], reverse=True)
    return scored[:keep]


def parse_llm_ranking(content: str, valid_ids: list[str]) -> list[dict] | None:
    """解析 LLM 精排输出；只保留池内 id（防幻觉），格式错误返回 None 走降级。"""
    try:
        text = content.strip()
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.S)
        start, end = text.find("["), text.rfind("]")
        if start == -1 or end == -1:
            return None
        arr = json.loads(text[start : end + 1])
        if not isinstance(arr, list):
            return None
        allow = set(valid_ids)
        out = []
        for row in arr:
            if isinstance(row, dict) and str(row.get("id", "")) in allow:
                try:
                    score = max(0, min(100, int(float(row.get("score", 0)))))
                except (TypeError, ValueError):
                    score = 0
                out.append(
                    {
                        "id": str(row["id"]),
                        "score": score,
                        "reason": str(row.get("reason", ""))[:80],
                    }
                )
        return out
    except (json.JSONDecodeError, ValueError) as e:
        logger.warning(f"LLM 精排输出解析失败：{e}")
        return None
