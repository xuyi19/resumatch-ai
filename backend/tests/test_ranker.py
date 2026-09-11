"""匹配排序算法测试"""
from app.matching.ranker import rank_jobs, score_one
from app.matching.feature_extractor import extract_resume_features


class FakeJob:
    """模拟 Job ORM 对象"""
    def __init__(self, id, title, company, city, tags, description,
                 experience="", education=""):
        self.id = id
        self.title = title
        self.company = company
        self.city = city
        self.tags = tags
        self.description = description
        self.experience = experience
        self.education = education


RESUME_TEXT = """
学历：本科
工作年限：3年
技能：Python, FastAPI, MySQL, Redis, Docker

工作经历：
负责后端开发，使用 Python + FastAPI 搭建微服务
"""


def test_high_match_job_scores_higher():
    """高匹配岗位分数应该高于低匹配"""
    resume = extract_resume_features(RESUME_TEXT)

    high_match = FakeJob(
        id=1, title="Python 后端开发工程师", company="A 公司", city="北京",
        tags=["Python", "FastAPI", "MySQL", "Redis"],
        description="负责后端开发",
        experience="3-5年", education="本科",
    )
    low_match = FakeJob(
        id=2, title="平面设计师", company="B 公司", city="北京",
        tags=["Photoshop", "AI"],
        description="负责平面设计",
        experience="1-3年", education="大专",
    )

    s1 = score_one(resume, high_match, use_semantic=False)
    s2 = score_one(resume, low_match, use_semantic=False)

    print(f"\n高匹配分数: {s1['score']}")
    print(f"低匹配分数: {s2['score']}")
    assert s1["score"] > s2["score"]


def test_rank_jobs_returns_top_k():
    """rank_jobs 应该返回 top_k 条并排序"""
    jobs = [
        FakeJob(1, "Python 工程师", "A", "北京",
                ["Python", "FastAPI"], "后端", "3-5年", "本科"),
        FakeJob(2, "Java 工程师", "B", "北京",
                ["Java", "Spring"], "后端", "3-5年", "本科"),
        FakeJob(3, "前端工程师", "C", "北京",
                ["JavaScript", "Vue"], "前端", "1-3年", "本科"),
        FakeJob(4, "数据分析师", "D", "北京",
                ["Python", "SQL"], "数据分析", "1-3年", "本科"),
        FakeJob(5, "产品经理", "E", "北京",
                ["需求分析"], "产品", "3-5年", "本科"),
    ]

    results = rank_jobs(RESUME_TEXT, jobs, top_k=3, use_semantic=False)
    assert len(results) == 3

    # 分数应该从高到低
    scores = [r["score"] for r in results]
    assert scores == sorted(scores, reverse=True)

    # 第一名应该是 Python 方向
    assert "Python" in results[0]["title"] or "数据" in results[0]["title"]