from fastapi import APIRouter, HTTPException, WebSocket, WebSocketDisconnect
from ..services.react_dev_server import react_manager
from ..core.config import settings

router = APIRouter(tags=["dev-server"])


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

