import re
from pathlib import Path
from urllib.parse import quote
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.deps import get_owner_id
from app.services.resume_service import ResumeService
from app.utils.docx_generator import generate_resume_docx

router = APIRouter(prefix="/resumes", tags=["resumes"])

# 证件照魔数白名单（JPG / PNG）
_PHOTO_MAGIC = {
    b"\xff\xd8\xff": ".jpg",
    b"\x89PNG\r\n\x1a\n": ".png",
}
_PHOTO_NAME_RE = re.compile(r"^[0-9a-f]{32}$")


class ResumeOut(BaseModel):
    id: int
    filename: str
    text_length: int


class ExportDocxRequest(BaseModel):
    optimized_resume: dict
    template: str = "classic"
    photo_id: str | None = None


@router.get("/templates")
async def get_templates():
    """简历模板目录（Word 导出版式）"""
    from app.utils.docx_generator import list_templates

    return {"items": list_templates()}


@router.post("/upload", response_model=ResumeOut)
async def upload_resume(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    if not file.filename:
        raise HTTPException(status_code=400, detail="缺少文件名")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="文件不能超过 10MB")

    service = ResumeService(db)
    try:
        resume = await service.upload_and_parse(file.filename, content, owner_id)
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
async def get_resume(
    resume_id: int,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    service = ResumeService(db)
    resume = await service.get_by_id(resume_id, owner_id)
    if not resume:
        raise HTTPException(status_code=404, detail="简历不存在")
    return ResumeOut(
        id=resume.id,
        filename=resume.filename,
        text_length=len(resume.raw_text),
    )


# ---------- 证件照 ----------

def _photo_dir() -> Path:
    path = Path(settings.PHOTOS_DIR)
    path.mkdir(parents=True, exist_ok=True)
    return path


@router.post("/photo")
async def upload_photo(file: UploadFile = File(...)):
    """上传证件照（JPG/PNG ≤5MB），返回 photo_id 供导出 Word 时嵌入"""
    content = await file.read()
    if len(content) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="照片不能超过 5MB")

    ext = next(
        (e for magic, e in _PHOTO_MAGIC.items() if content.startswith(magic)),
        None,
    )
    if not ext:
        raise HTTPException(status_code=400, detail="仅支持 JPG / PNG 格式照片")

    photo_id = uuid4().hex
    path = _photo_dir() / f"{photo_id}{ext}"
    path.write_bytes(content)
    return {"photo_id": photo_id}


@router.get("/photo/{photo_id}")
async def get_photo(photo_id: str):
    """读取证件照（前端预览）"""
    if not _PHOTO_NAME_RE.match(photo_id):
        raise HTTPException(status_code=404, detail="照片不存在")
    path = next(
        (p for p in _photo_dir().glob(f"{photo_id}.*") if p.is_file()), None
    )
    if not path:
        raise HTTPException(status_code=404, detail="照片不存在")

    media = "image/jpeg" if path.suffix == ".jpg" else "image/png"
    return Response(content=path.read_bytes(), media_type=media)


@router.delete("/photo/{photo_id}")
async def delete_photo(photo_id: str):
    if not _PHOTO_NAME_RE.match(photo_id):
        raise HTTPException(status_code=404, detail="照片不存在")
    removed = False
    for p in _photo_dir().glob(f"{photo_id}.*"):
        p.unlink(missing_ok=True)
        removed = True
    if not removed:
        raise HTTPException(status_code=404, detail="照片不存在")
    return {"message": "已删除"}


# ---------- Word 导出 ----------

@router.post("/export-docx")
async def export_docx(req: ExportDocxRequest):
    """把优化后的简历导出为 Word 文件（可选嵌入证件照）"""
    photo_path = None
    if req.photo_id:
        if not _PHOTO_NAME_RE.match(req.photo_id):
            raise HTTPException(status_code=404, detail="照片不存在")
        found = next(
            (p for p in _photo_dir().glob(f"{req.photo_id}.*") if p.is_file()), None
        )
        if not found:
            raise HTTPException(status_code=404, detail="照片不存在")
        photo_path = found

    try:
        data = generate_resume_docx(
            req.optimized_resume, template=req.template, photo_path=photo_path
        )
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
