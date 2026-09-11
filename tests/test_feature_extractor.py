"""特征提取测试 —— 匹配算法的基础"""
from app.matching.feature_extractor import (
    extract_skills,
    extract_education,
    extract_experience_years,
    extract_resume_features,
)


def test_extract_skills_basic():
    text = "熟悉 Python、FastAPI、MySQL 和 Redis 缓存"
    skills = extract_skills(text)
    assert "python" in skills
    assert "fastapi" in skills
    assert "mysql" in skills
    assert "redis" in skills
    assert "java" not in skills


def test_extract_skills_case_insensitive():
    text = "PYTHON / FastAPI / JavaScript"
    skills = extract_skills(text)
    assert "python" in skills
    assert "fastapi" in skills
    assert "javascript" in skills


def test_extract_education():
    assert extract_education("学历：本科") == 3
    assert extract_education("硕士学历") == 4
    assert extract_education("博士") == 5
    assert extract_education("大专") == 2
    assert extract_education("不限") == 0


def test_extract_experience_years():
    lo, hi = extract_experience_years("3-5年")
    assert lo == 3.0 and hi == 5.0

    lo, hi = extract_experience_years("5年以上")
    assert lo == 5.0 and hi == 99.0

    lo, hi = extract_experience_years("经验不限")
    assert lo == 0.0 and hi == 99.0


def test_extract_resume_features_full():
    text = """
    学历：本科
    工作年限：3年
    技能：Python, FastAPI, MySQL, Redis, Docker
    """
    f = extract_resume_features(text)
    assert f.education_level == 3
    assert f.experience_years == 3.0
    assert "python" in f.skills
    assert "fastapi" in f.skills
    assert len(f.skills) >= 5