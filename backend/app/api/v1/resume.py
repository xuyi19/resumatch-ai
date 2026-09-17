from urllib.parse import quote

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import get_db
from app.services.resume_service import ResumeService
from app.utils.docx_generator import generate_resume_docx

router = APIRouter(prefix="/resumes", tags=["resumes"])


class ResumeOut(BaseModel):
    id: int
    filename: str
    text_length: int


class ExportDocxRequest(BaseModel):
    optimized_resume: dict
    template: str = "classic"
@router.post("/upload", response_model=ResumeOut)
async def upload_resume(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
):
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


@router.post("/export-docx")
async def export_docx(req: ExportDocxRequest):
    """把优化后的简历导出为 Word 文件"""
    try:
        data = generate_resume_docx(req.optimized_resume, template=req.template)   # ★ 传参
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成失败: {e}")

    filename = quote("优化后的简历.docx")
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{filename}",
        },
    )