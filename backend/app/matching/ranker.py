from loguru import logger

from app.matching.feature_extractor import (
    extract_job_features, extract_resume_features,
)
from app.matching.semantic_matcher import semantic_similarity

WEIGHTS = {"skill": 0.40, "semantic": 0.30, "experience": 0.20, "education": 0.10}


def _skill_score(resume, job) -> float:
    if not job.skills:
        return 0.5
    if not resume.skills:
        return 0.0
    return len(resume.skills & job.skills) / len(job.skills)


def _experience_score(resume, job) -> float:
    y = resume.experience_years
    lo, hi = job.experience_years_min, job.experience_years_max
    if lo <= y <= hi:
        return 1.0
    if y < lo:
        return max(0.0, 1.0 - (lo - y) * 0.2)
    return max(0.0, 1.0 - (y - hi) * 0.1)


def _education_score(resume, job) -> float:
    if job.education_level == 0:
        return 1.0
    if resume.education_level >= job.education_level:
        return 1.0
    return max(0.0, 1.0 - (job.education_level - resume.education_level) * 0.3)


def score_one(resume, job_obj, use_semantic=True) -> dict:
    job = extract_job_features(job_obj)

    s_skill = _skill_score(resume, job)
    s_exp = _experience_score(resume, job)
    s_edu = _education_score(resume, job)
    s_sem = semantic_similarity(resume.raw_text, job.raw_text) if use_semantic else 0.5

    total = (
        s_skill * WEIGHTS["skill"] + s_sem * WEIGHTS["semantic"]
        + s_exp * WEIGHTS["experience"] + s_edu * WEIGHTS["education"]
    )

    return {
        "score": round(total * 100, 2),
        "breakdown": {
            "skill": round(s_skill * 100, 2),
            "semantic": round(s_sem * 100, 2),
            "experience": round(s_exp * 100, 2),
            "education": round(s_edu * 100, 2),
        },
        "matched_skills": sorted(resume.skills & job.skills),
        "missing_skills": sorted(job.skills - resume.skills)[:10],
    }


def rank_jobs(resume_text: str, jobs: list, top_k: int = 10,
              use_semantic: bool = True) -> list:
    resume = extract_resume_features(resume_text)
    results = []
    for job in jobs:
        try:
            detail = score_one(resume, job, use_semantic=use_semantic)
            is_dict = isinstance(job, dict)
            results.append({
                "job_id": job.get("id") if is_dict else job.id,
                "title": job.get("title") if is_dict else job.title,
                "company": job.get("company") if is_dict else job.company,
                "city": job.get("city") if is_dict else job.city,
                **detail,
            })
        except Exception as e:
            logger.warning(f"打分失败: {e}")
            continue
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]