from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
import logging
import shutil

from ..core.config import settings
from ..services.react_dev_server import create_react_manager
from ..services.template_service import get_template_service


router = APIRouter(tags=["project"])

# 로거 설정
logger = logging.getLogger("app.project")


class ProjectInitRequest(BaseModel):
    componentCode: str = ""
    dependencies: dict[str, str] = {}
    description: str = ""
    app_name: str = "dynamic-react-app"
    title: str = "Dynamic React App"
    project_name: str = "default-project"  # 프로젝트 이름 추가

class ProjectDeleteRequest(BaseModel):
    project_name: str

@router.post("/init-project")
async def init_project(request: ProjectInitRequest):
    try:
        # 프로젝트 이름에 따라 동적으로 경로 설정
        base_projects_dir = settings.REACT_PROJECT_PATH.parent / "projects"
        project_path: Path = base_projects_dir / request.project_name
        
        # 프로젝트 디렉토리가 없다면 생성
        base_projects_dir.mkdir(exist_ok=True)

        # 기존 프로젝트가 있으면 바로 개발 서버 실행
        if project_path.exists():
            project_react_manager = create_react_manager(project_path, settings.REACT_DEV_PORT)
            await project_react_manager.start()
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
            "title": request.title,
            "project_name": request.project_name,
            "description": request.description,
        }
        template_service.customize_template(project_path, customizations)

        logger.info(f"프로젝트 경로: {project_path}")
        logger.info(f"템플릿 기반 프로젝트 생성 완료: {request.app_name}")

        # 의존성 설치 및 개발 서버 시작
        project_react_manager = create_react_manager(project_path, settings.REACT_DEV_PORT)
        await project_react_manager.install_dependencies()
        await project_react_manager.ensure_typescript_and_router()
        await project_react_manager.start()

        dev_server_url = f"http://localhost:{settings.REACT_DEV_PORT}/"
        return {
            "success": True,
            "message": "Project initialized from template and dev server started",
            "devServerUrl": dev_server_url,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to prepare or initialize project: {e}")

@router.delete("/delete-project")
async def delete_project(request: ProjectDeleteRequest):
    try:
        # 프로젝트 경로 설정
        base_projects_dir = settings.REACT_PROJECT_PATH.parent / "projects"
        project_path: Path = base_projects_dir / request.project_name
        
        # 프로젝트 디렉토리가 존재하지 않으면 404
        if not project_path.exists():
            raise HTTPException(status_code=404, detail=f"Project '{request.project_name}' not found")
        
        # 프로젝트 디렉토리인지 확인 (안전성 체크)
        if not project_path.is_dir():
            raise HTTPException(status_code=400, detail=f"'{request.project_name}' is not a directory")
        
        # 프로젝트 디렉토리가 base_projects_dir 하위에 있는지 확인 (보안 체크)
        try:
            project_path.resolve().relative_to(base_projects_dir.resolve())
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid project path")
        
        # 프로젝트 폴더 삭제
        shutil.rmtree(project_path)
        
        logger.info(f"프로젝트 삭제 완료: {request.project_name} at {project_path}")
        
        return {
            "success": True,
            "message": f"Project '{request.project_name}' deleted successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"프로젝트 삭제 실패: {request.project_name} - {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete project: {str(e)}")