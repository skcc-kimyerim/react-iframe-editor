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
    attachments: list[dict] = []
    description: str = ""
    app_name: str = "dynamic-react-app"
    title: str = "Dynamic React App"
    style_preferences: str = ""  # 스타일 선호도 (예: "modern", "minimalist", "colorful")

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

        # 프로젝트가 없는 경우 - 스마트 생성 진행
        # description, attachments, style_preferences 중 하나라도 있으면 스마트 생성
        can_generate_smart = (
            request.description.strip() or 
            request.attachments or 
            request.style_preferences.strip()
        )
        
        if not can_generate_smart:
            raise HTTPException(
                status_code=400, 
                detail="프로젝트 생성을 위해 설명(description), 첨부파일(attachments), 또는 스타일 선호도(style_preferences) 중 하나 이상이 필요합니다."
            )
        
        # LLM을 사용한 스마트 프로젝트 생성
        logger.info("스마트 프로젝트 생성 모드로 진행")
        return await _generate_smart_project(request, project_path)
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to prepare or initialize project: {e}")


async def _generate_smart_project(request: ProjectInitRequest, project_path: Path):
    """LLM을 사용하여 스마트 프로젝트 생성"""
    from ..services.agents.smart_template_agent import SmartTemplateAgent
    
    # 스마트 템플릿 에이전트를 사용하여 프로젝트 생성
    smart_agent = SmartTemplateAgent()
    
    # LLM을 통해 프로젝트 구조와 컴포넌트들을 생성
    generation_result = await smart_agent.generate_project(
        description=request.description,
        attachments=request.attachments,
        style_preferences=request.style_preferences,
        app_name=request.app_name,
        title=request.title
    )
    
    if not generation_result.get("success"):
        raise HTTPException(
            status_code=500, 
            detail=f"스마트 프로젝트 생성 실패: {generation_result.get('message', '알 수 없는 오류')}"
        )

    # 생성된 프로젝트를 실제 파일 시스템에 적용
    template_service = get_template_service()
    
    # 먼저 기본 템플릿 복사
    dependencies = {**request.dependencies, **generation_result.get("dependencies", {})}
    success = template_service.copy_template(project_path, dependencies)
    if not success:
        raise HTTPException(status_code=500, detail="Failed to copy base template")

    # LLM이 생성한 커스터마이징 적용
    customizations = {
        "app_name": request.app_name,
        "port": settings.REACT_DEV_PORT,
        "title": request.title
    }
    template_service.customize_template(project_path, customizations)
    
    # LLM이 생성한 컴포넌트들과 페이지들을 실제 파일로 생성
    await smart_agent.apply_generated_files(project_path, generation_result.get("generated_files", []))

    logger.info(f"스마트 프로젝트 생성 완료: {request.app_name}")

    # 의존성 설치 및 개발 서버 시작
    await react_manager.install_dependencies()
    await react_manager.ensure_typescript_and_router()
    await react_manager.start()

    dev_server_url = f"http://localhost:{settings.REACT_DEV_PORT}/"
    return {
        "success": True,
        "message": "Smart project generated and dev server started",
        "devServerUrl": dev_server_url,
        "generationSummary": generation_result.get("summary", "스마트 프로젝트가 성공적으로 생성되었습니다."),
        "generatedComponents": generation_result.get("component_list", [])
    }

