from fastapi import APIRouter, UploadFile, File, HTTPException
from fastapi.responses import FileResponse
from typing import List
from pathlib import Path
import uuid
from ..core.config import settings


router = APIRouter(tags=["uploads"])


def _ensure_upload_dir() -> Path:
    upload_dir = settings.UPLOAD_DIR
    upload_dir.mkdir(parents=True, exist_ok=True)
    return upload_dir


@router.post("/uploads", summary="Upload one or more files")
async def upload_files(files: List[UploadFile] = File(...)):
    try:
        saved = []
        upload_dir = _ensure_upload_dir()
        for f in files:
            ext = Path(f.filename or "").suffix
            safe_name = uuid.uuid4().hex + (ext if ext else "")
            dest = upload_dir / safe_name
            content = await f.read()
            dest.write_bytes(content)
            saved.append({
                "filename": f.filename,
                "stored": safe_name,
                "url": f"/api/uploads/{safe_name}",
                "mime": f.content_type,
                "size": len(content),
            })
        return {"files": saved}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/uploads/{name}", response_class=FileResponse)
async def get_uploaded_file(name: str):
    file_path = _ensure_upload_dir() / name
    if not file_path.exists() or not file_path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(file_path))

