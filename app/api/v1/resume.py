from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.services.diagnosis_service import DiagnosisService
from app.services.resume_service import ResumeService

router = APIRouter(prefix="/resumes", tags=["resumes"])


class ResumeOut(BaseModel):
    id: int
    filename: str
    text_length: int


class DiagnoseRequest(BaseModel):
    resume_text: str
    jd_text: str = ""


@router.post("/upload", response_model=ResumeOut)
async def upload_resume(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
    """上传简历（支持 pdf/docx/txt），解析文本并入库"""
    if not file.filename:
        raise HTTPException(status_code=400, detail="缺少文件名")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件不能超过 10MB")

    service = ResumeService(db)
    try:
        resume = await service.upload_and_parse(file.filename, content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"解析失败: {e}")

    return ResumeOut(
        id=resume.id,
        filename=resume.filename,
        text_length=len(resume.raw_text),
    )


@router.get("/{resume_id}", response_model=ResumeOut)
async def get_resume(resume_id: int, db: AsyncSession = Depends(get_db)):
    service = ResumeService(db)
    resume = await service.get_by_id(resume_id)
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在")
    return ResumeOut(
        id=resume.id,
        filename=resume.filename,
        text_length=len(resume.raw_text),
    )


@router.post("/diagnose")
async def diagnose(req: DiagnoseRequest):
    """简历 + JD → 多智能体诊断（不落库，纯计算）"""
    service = DiagnosisService()
    return await service.diagnose(req.resume_text, req.jd_text)