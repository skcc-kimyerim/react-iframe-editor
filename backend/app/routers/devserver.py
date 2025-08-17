from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from pathlib import Path
from ..services.react_dev_server import react_manager, create_react_manager
from ..core.config import settings

router = APIRouter(tags=["dev-server"])


class DevServerRequest(BaseModel):
    projectName: str = "default-project"


@router.post("/start-dev-server")
async def start_dev_server(request: DevServerRequest):
    try:
        # 프로젝트별 경로 설정
        base_projects_dir = settings.REACT_PROJECT_PATH.parent / "projects"
        project_path = base_projects_dir / request.projectName
        
        if not project_path.exists():
            raise HTTPException(status_code=400, detail=f"Project '{request.projectName}' not found. Please initialize first.")
        
        # 프로젝트별 React 관리자 생성 및 시작
        project_react_manager = create_react_manager(project_path, settings.REACT_DEV_PORT)
        await project_react_manager.start()
        
        dev_server_url = f"http://localhost:{settings.REACT_DEV_PORT}/"
        return {"success": True, "devServerUrl": dev_server_url, "message": "React dev server started successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to start dev server: {str(e)}")


@router.post("/stop-dev-server")
async def stop_dev_server(request: DevServerRequest):
    try:
        # 프로젝트별 경로 설정
        base_projects_dir = settings.REACT_PROJECT_PATH.parent / "projects"
        project_path = base_projects_dir / request.projectName
        
        # 프로젝트별 React 관리자 생성 및 중지
        project_react_manager = create_react_manager(project_path, settings.REACT_DEV_PORT)
        await project_react_manager.stop()
        
        return {"success": True, "message": "React dev server stopped"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to stop dev server: {str(e)}")


@router.websocket("/dev-server/logs")
async def dev_server_logs(ws: WebSocket):
    await ws.accept()
    queue = react_manager.subscribe()
    # send initial buffer
    try:
        for msg in react_manager.get_buffer():
            await ws.send_json({"type": "log", **msg})
        while True:
            msg = await queue.get()
            await ws.send_json({"type": "log", **msg})
    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await ws.close(code=1011)
        except Exception:
            pass
    finally:
        react_manager.unsubscribe(queue)

