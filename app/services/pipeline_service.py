from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.entities import Job, Resume
from app.services.diagnosis_service import DiagnosisService
from app.services.match_service import MatchService


class PipelineService:
    """编排：简历 → 匹配 → 诊断"""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.match_service = MatchService(db)
        self.diagnosis_service = DiagnosisService()

    async def run(
        self,
        resume_text: str,
        top_k: int = 10,
        diagnose_job_id: int | None = None,
        skip_diagnosis: bool = False,
    ) -> dict:
        # 1. 匹配 Top-N
        logger.info(f"开始匹配，简历 {len(resume_text)} 字，top_k={top_k}")
        top_jobs = await self.match_service.recommend(
            resume_text, top_k=top_k, use_semantic=True
        )
        if not top_jobs:
            return {"error": "没有匹配到任何岗位", "top_jobs": []}

        result: dict = {
            "top_jobs": top_jobs,
            "diagnosis_target": None,
            "diagnosis": None,
        }

        if skip_diagnosis:
            return result

        # 2. 选定目标岗位
        if diagnose_job_id is not None:
            target = next(
                (j for j in top_jobs if j["job_id"] == diagnose_job_id), None
            )
            if target is None:
                # 从数据库单独查（可能是 Top-N 外的岗位）
                job = await self.db.get(Job, diagnose_job_id)
                if job is None:
                    result["error"] = f"岗位 id={diagnose_job_id} 不存在"
                    return result
                target = {
                    "job_id": job.id,
                    "title": job.title,
                    "company": job.company,
                    "city": job.city,
                }
        else:
            target = top_jobs[0]

        # 3. 拉完整的岗位 JD
        job = await self.db.get(Job, target["job_id"])
        if job is None:
            result["error"] = "目标岗位不存在"
            return result

        # 4. 多智能体诊断
        logger.info(f"开始诊断，目标岗位: {job.title} @ {job.company}")
        jd_text = f"""岗位：{job.title}
公司：{job.company}
城市：{job.city}
经验要求：{job.experience or '不限'}
学历要求：{job.education or '不限'}
技能标签：{', '.join(job.tags or [])}

岗位描述：
{job.description}
"""
        diagnosis = await self.diagnosis_service.diagnose(resume_text, jd_text)

        result["diagnosis_target"] = target
        result["diagnosis"] = diagnosis
        return result