from fastapi import APIRouter, HTTPException
from ..core.config import settings
from ..services.files import build_file_tree, resolve_src_path

router = APIRouter(tags=["files"])


@router.get("/files")
async def get_files():
    base_dir = settings.REACT_PROJECT_PATH
    if not base_dir.exists():
        return {"tree": []}
    try:
        tree = build_file_tree(base_dir, "")
        return {"tree": tree}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file tree: {str(e)}")


@router.get("/file")
async def read_file(relativePath: str):
    try:
        file_path = resolve_src_path(relativePath)
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        content = file_path.read_text(encoding="utf-8")
        return {"content": content}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")


from pydantic import BaseModel


class FileSaveRequest(BaseModel):
    relativePath: str
    content: str


@router.put("/file")
async def save_file(payload: FileSaveRequest):
    try:
        file_path = resolve_src_path(payload.relativePath)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(payload.content, encoding="utf-8")
        return {"success": True, "message": "File saved successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

