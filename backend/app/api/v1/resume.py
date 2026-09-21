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
    # 桌面形态专用：用户通过原生另存为对话框选择的绝对路径，服务端直写该文件。
    # 网页形态禁止（服务端不得写用户任意路径），为空时走浏览器 blob 下载。
    save_path: str | None = None


@router.get("/export-history")
async def list_export_history(
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """导出历史（最近 30 条，按时间倒序）"""
    from sqlalchemy import select

    from app.models.entities import ExportHistory

    res = await db.execute(
        select(ExportHistory)
        .where(ExportHistory.owner_id == owner_id)
        .order_by(ExportHistory.id.desc())
        .limit(30)
    )
    items = [
        {
            "id": r.id,
            "filename": r.filename,
            "save_path": r.save_path,
            "template": r.template,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in res.scalars()
    ]
    return {"items": items}


@router.delete("/export-history/{history_id}")
async def delete_export_history(
    history_id: int,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    from sqlalchemy import select

    from app.models.entities import ExportHistory

    res = await db.execute(
        select(ExportHistory).where(
            ExportHistory.id == history_id, ExportHistory.owner_id == owner_id
        )
    )
    rec = res.scalars().first()
    if not rec:
        raise HTTPException(status_code=404, detail="记录不存在")
    await db.delete(rec)
    await db.commit()
    return {"message": "已删除"}


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

def _validate_save_path(save_path: str) -> Path:
    """桌面形态保存路径校验：绝对路径 + .docx 后缀 + 父目录存在。"""
    if settings.APP_MODE != "local":
        raise HTTPException(status_code=403, detail="网页形态不支持指定保存路径")
    p = Path(save_path)
    if not p.is_absolute():
        raise HTTPException(status_code=400, detail="保存路径必须是绝对路径")
    if p.suffix.lower() != ".docx":
        raise HTTPException(status_code=400, detail="保存路径必须以 .docx 结尾")
    if not p.parent.is_dir():
        raise HTTPException(status_code=400, detail=f"目录不存在：{p.parent}")
    return p


async def _record_export(
    db: AsyncSession, owner_id: str, filename: str, save_path: str | None, template: str
) -> None:
    from app.models.entities import ExportHistory

    db.add(
        ExportHistory(
            owner_id=owner_id,
            filename=filename,
            save_path=save_path,
            template=template,
        )
    )
    await db.commit()


@router.post("/export-docx")
async def export_docx(
    req: ExportDocxRequest,
    db: AsyncSession = Depends(get_db),
    owner_id: str = Depends(get_owner_id),
):
    """把优化后的简历导出为 Word 文件（可选嵌入证件照）。

    save_path 为空：浏览器 blob 下载（网页形态主路径），记录导出历史（无路径）。
    save_path 非空（仅桌面形态）：服务端直写用户选择的路径，返回 JSON。
    """
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

    filename = "优化后的简历.docx"

    if req.save_path:
        target = _validate_save_path(req.save_path)
        try:
            target.write_bytes(data)
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"写入文件失败: {e}")
        await _record_export(db, owner_id, target.name, str(target), req.template)
        return {"saved_to": str(target), "filename": target.name}

    await _record_export(db, owner_id, filename, None, req.template)
    quoted = quote(filename)
    return Response(
        content=data,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{quoted}",
        },
    )
