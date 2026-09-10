from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.services.match_service import MatchService
from app.services.pipeline_service import PipelineService
from app.services.resume_service import ResumeService

router = APIRouter(prefix="/match", tags=["match"])


class MatchRequest(BaseModel):
    resume_text: str
    top_k: int = 10
    use_semantic: bool = True


class MatchWithDiagnosisRequest(BaseModel):
    resume_id: int | None = None
    resume_text: str | None = None
    top_k: int = 10
    diagnose_job_id: int | None = None   # 不传则诊断 Top1
    skip_diagnosis: bool = False          # 只做匹配，不做诊断


@router.post("/recommend")
async def recommend(req: MatchRequest, db: AsyncSession = Depends(get_db)):
    """简历文本 → Top-N 岗位（纯匹配，不诊断）"""
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
    """
    完整流程：简历 → 匹配 Top-N → 对目标岗位做多智能体诊断。
    ★ 这个接口会很慢（30-60 秒），因为要等 4 个 Agent 串行跑完。
    """
    # 解析简历来源
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
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"流水线失败: {e}")

    if result.get("error"):
        raise HTTPException(status_code=400, detail=result["error"])

    return result