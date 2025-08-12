from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
import logging

from ..core.config import settings
from ..services.react_dev_server import react_manager
from ..services.template_service import get_template_service


router = APIRouter(tags=["project"])

# 로거 설정
logger = logging.getLogger("app.project")


class ProjectInitRequest(BaseModel):
    componentCode: str = ""
    dependencies: dict[str, str] = {}
    app_name: str = "dynamic-react-app"
    title: str = "Dynamic React App"


@router.post("/init-project")
async def init_project(request: ProjectInitRequest):
    try:
        project_path: Path = settings.REACT_PROJECT_PATH

        # 기존 프로젝트가 있으면 바로 개발 서버 실행
        if project_path.exists():
            await react_manager.start()
            dev_server_url = f"http://localhost:{settings.REACT_DEV_PORT}/"
            return {
                "success": True,
                "message": "Existing project detected. Dev server started",
                "devServerUrl": dev_server_url,
            }

        # 템플릿 서비스 인스턴스 생성
        template_service = get_template_service()

        # 템플릿에서 프로젝트 복사
        success = template_service.copy_template(project_path, request.dependencies)
        if not success:
            raise HTTPException(status_code=500, detail="Failed to copy template")

        # 사용자 정의 설정 적용
        customizations = {
            "app_name": request.app_name,
            "port": settings.REACT_DEV_PORT,
            "title": request.title
        }
        template_service.customize_template(project_path, customizations)

        logger.info(f"프로젝트 경로: {project_path}")
        logger.info(f"템플릿 기반 프로젝트 생성 완료: {request.app_name}")

        # 의존성 설치 및 개발 서버 시작
        await react_manager.install_dependencies()
        await react_manager.ensure_typescript_and_router()
        await react_manager.start()

        dev_server_url = f"http://localhost:{settings.REACT_DEV_PORT}/"
        return {
            "success": True,
            "message": "Project initialized from template and dev server started",
            "devServerUrl": dev_server_url,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to prepare or initialize project: {e}")

