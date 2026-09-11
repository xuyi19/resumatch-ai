import re
from dataclasses import dataclass, field


SKILL_KEYWORDS = {
    "python", "java", "javascript", "typescript", "go", "golang", "c++", "c#",
    "rust", "php", "ruby", "scala", "kotlin", "swift", "matlab", "shell", "bash",
    "fastapi", "django", "flask", "spring", "springboot", "spring cloud",
    "mybatis", "hibernate", "express", "nestjs", "gin",
    "vue", "react", "angular", "html", "html5", "css", "css3",
    "webpack", "vite", "elementui", "antd", "uni-app", "flutter",
    "mysql", "postgresql", "oracle", "sqlserver", "mongodb", "redis", "elasticsearch",
    "clickhouse", "hbase", "sqlite", "sql",
    "hadoop", "spark", "flink", "hive", "kafka", "storm",
    "pytorch", "tensorflow", "keras", "sklearn", "xgboost", "lightgbm",
    "transformer", "bert", "gpt", "llm", "langchain", "langgraph", "rag", "agent",
    "nlp", "opencv", "yolo", "numpy", "pandas", "matplotlib",
    "docker", "kubernetes", "k8s", "jenkins", "ansible", "terraform",
    "prometheus", "grafana", "nginx", "linux", "git", "maven",
    "restful", "grpc", "websocket", "rabbitmq", "rocketmq", "zookeeper", "nacos",
}

EDU_LEVELS = {
    "不限": 0, "学历不限": 0, "高中": 1, "中专": 1,
    "大专": 2, "本科": 3, "学士": 3, "硕士": 4, "研究生": 4, "博士": 5,
}


@dataclass
class ResumeFeatures:
    skills: set = field(default_factory=set)
    education_level: int = 0
    experience_years: float = 0.0
    raw_text: str = ""


@dataclass
class JobFeatures:
    skills: set = field(default_factory=set)
    education_level: int = 0
    experience_years_min: float = 0.0
    experience_years_max: float = 99.0
    raw_text: str = ""


def extract_skills(text: str) -> set:
    text_lower = text.lower()
    return {kw for kw in SKILL_KEYWORDS if kw in text_lower}


def extract_education(text: str) -> int:
    max_level = 0
    for name, level in EDU_LEVELS.items():
        if name in text:
            max_level = max(max_level, level)
    return max_level


def extract_experience_years(text: str) -> tuple:
    m = re.search(r"(\d+)\s*[-~]\s*(\d+)\s*年", text)
    if m:
        return float(m.group(1)), float(m.group(2))
    m = re.search(r"(\d+)\s*年以上", text)
    if m:
        return float(m.group(1)), 99.0
    return 0.0, 99.0


def extract_resume_features(text: str) -> ResumeFeatures:
    years = 0.0

    # 模式 1：3年经验 / 3年工作经验 / 3年开发经验
    m = re.search(r"(\d+(?:\.\d+)?)\s*年.{0,4}(工作|经验|开发)", text)
    if m:
        years = float(m.group(1))
    else:
        # 模式 2：工作年限：3年 / 经验：3年 / 工作年限 3 年
        m = re.search(r"(工作年限|工作经验|经验|工作)\s*[:：]?\s*(\d+(?:\.\d+)?)\s*年", text)
        if m:
            years = float(m.group(2))

    return ResumeFeatures(
        skills=extract_skills(text),
        education_level=extract_education(text),
        experience_years=years,
        raw_text=text,
    )


def extract_job_features(job) -> JobFeatures:
    if hasattr(job, "tags"):
        tags = job.tags or []
        title = job.title
        desc = job.description
        exp_str = job.experience or ""
    else:
        tags = job.get("tags", [])
        title = job["title"]
        desc = job["description"]
        exp_str = job.get("experience") or ""

    text = f"{title} {desc} {' '.join(tags)}"
    skills = extract_skills(text)
    for t in tags:
        t_low = str(t).lower().strip()
        if t_low in SKILL_KEYWORDS:
            skills.add(t_low)

    edu = extract_education(text)
    lo, hi = extract_experience_years(exp_str or text)

    return JobFeatures(
        skills=skills, education_level=edu,
        experience_years_min=lo, experience_years_max=hi,
        raw_text=text,
    )