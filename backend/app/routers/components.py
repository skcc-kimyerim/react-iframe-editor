from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ..core.config import settings

router = APIRouter(tags=["components"])


class ComponentUpdateRequest(BaseModel):
    content: str


@router.put("/component/{filename}")
async def update_component(filename: str, request: ComponentUpdateRequest):
    try:
        file_path = settings.REACT_PROJECT_PATH / "src" / filename
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(request.content)
        return {"success": True, "message": "Component updated successfully"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update component: {str(e)}")

