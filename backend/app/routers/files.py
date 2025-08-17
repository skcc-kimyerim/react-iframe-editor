from fastapi import APIRouter, HTTPException
from ..core.config import settings
from ..services.files import build_file_tree, resolve_src_path

router = APIRouter(tags=["files"])


@router.get("/files")
async def get_files(projectName: str = "default-project"):
    from pathlib import Path
    # 프로젝트별 경로 설정
    base_projects_dir = settings.REACT_PROJECT_PATH.parent / "projects"
    project_dir = base_projects_dir / projectName
    
    if not project_dir.exists():
        return {"tree": []}
    try:
        tree = build_file_tree(project_dir, "")
        return {"tree": tree}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file tree: {str(e)}")


@router.get("/file")
async def read_file(relativePath: str, projectName: str = "default-project"):
    try:
        file_path = resolve_src_path(relativePath, projectName)
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
    projectName: str = "default-project"


@router.put("/file")
async def save_file(payload: FileSaveRequest):
    try:
        file_path = resolve_src_path(payload.relativePath, payload.projectName)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(payload.content, encoding="utf-8")
        return {"success": True, "message": "File saved successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")

