from fastapi import APIRouter, HTTPException
from ..services.react_dev_server import react_manager
from ..core.config import settings

router = APIRouter(tags=["devserver"])


@router.post("/start-dev-server")
async def start_dev_server():
    try:
        if not settings.REACT_PROJECT_PATH.exists():
            raise HTTPException(status_code=400, detail="React project not initialized. Please initialize first.")
        await react_manager.start()
        dev_server_url = f"http://localhost:{settings.REACT_DEV_PORT}/"
        return {"success": True, "devServerUrl": dev_server_url, "message": "React dev server started successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start dev server: {str(e)}")


@router.post("/stop-dev-server")
async def stop_dev_server():
    await react_manager.stop()
    return {"success": True, "message": "React dev server stopped"}

