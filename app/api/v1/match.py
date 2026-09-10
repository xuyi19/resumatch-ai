from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.services.match_service import MatchService
from app.services.pipeline_service import PipelineService
from app.services.resume_service import ResumeService

router = APIRouter(prefix="/match", tags=["match"])


class LLMConfig(BaseModel):
    api_key: str | None = None
    base_url: str | None = None
    model: str | None = None


class MatchRequest(BaseModel):
    resume_text: str
    top_k: int = 10
    use_semantic: bool = True


class MatchWithDiagnosisRequest(BaseModel):
    resume_id: int | None = None
    resume_text: str | None = None
    top_k: int = 10
    diagnose_job_id: int | None = None
    skip_diagnosis: bool = False
    llm_config: LLMConfig | None = None


@router.post("/recommend")
async def recommend(req: MatchRequest, db: AsyncSession = Depends(get_db)):
    service = MatchService(db)
    results = await service.recommend(
        resume_text=req.resume_text,
        top_k=req.top_k,
        use_semantic=req.use_semantic,
    )
    return {"count": len(results), "results": results}


@router.post("/with-diagnosis")
async def match_with_diagnosis(
    req: MatchWithDiagnosisRequest,
    db: AsyncSession = Depends(get_db),
):
    if req.resume_id is not None:
        resume_service = ResumeService(db)
        resume = await resume_service.get_by_id(req.resume_id)
        if resume is None:
            raise HTTPException(status_code=404, detail="简历不存在")
        resume_text = resume.raw_text
    elif req.resume_text:
        resume_text = req.resume_text
    else:
        raise HTTPException(status_code=400, detail="必须提供 resume_id 或 resume_text")

    service = PipelineService(db)
    try:
        result = await service.run(
            resume_text=resume_text,
            top_k=req.top_k,
            diagnose_job_id=req.diagnose_job_id,
            skip_diagnosis=req.skip_diagnosis,
            llm_config=req.llm_config.model_dump() if req.llm_config else None,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"流水线失败: {e}")

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return result