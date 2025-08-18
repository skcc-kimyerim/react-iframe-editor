from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from pydantic import BaseModel
from pathlib import Path
from ..services.react_dev_server import react_manager, get_or_create_manager, stop_current_manager, get_current_project_name
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
        
        # 전역 매니저를 통한 프로젝트 서버 관리 (이전 서버 자동 종료 후 새 서버 시작)
        project_react_manager = await get_or_create_manager(request.projectName, project_path, settings.REACT_DEV_PORT)
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
        # 현재 실행 중인 프로젝트 확인
        current_project = get_current_project_name()
        
        if current_project == request.projectName:
            # 요청된 프로젝트가 현재 실행 중인 프로젝트와 일치하면 중지
            success = await stop_current_manager()
            if success:
                return {"success": True, "message": f"React dev server for '{request.projectName}' stopped"}
            else:
                return {"success": False, "message": f"No running server found for '{request.projectName}'"}
        else:
            return {"success": False, "message": f"'{request.projectName}' is not currently running. Current project: {current_project or 'None'}"}
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

