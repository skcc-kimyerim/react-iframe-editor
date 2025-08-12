import json
import shutil
from pathlib import Path
from typing import Dict, Any
import logging

logger = logging.getLogger("app.template_service")


class TemplateService:
    """React 프로젝트 템플릿 복사 및 설정 서비스"""

    def __init__(self, template_dir: Path):
        self.template_dir = template_dir

    def copy_template(self, target_dir: Path, dependencies: Dict[str, str] = None) -> bool:
        """
        템플릿 디렉토리를 타겟 디렉토리로 복사하고 설정을 업데이트합니다.
        
        Args:
            target_dir: 복사될 대상 디렉토리
            dependencies: 추가할 의존성 패키지들
            
        Returns:
            bool: 복사 성공 여부
        """
        try:
            if not self.template_dir.exists():
                logger.error(f"템플릿 디렉토리가 존재하지 않습니다: {self.template_dir}")
                return False

            # 템플릿 디렉토리 전체 복사
            shutil.copytree(self.template_dir, target_dir, dirs_exist_ok=True)
            logger.info(f"템플릿 복사 완료: {self.template_dir} -> {target_dir}")

            # package.json 업데이트 (dependencies가 있는 경우)
            if dependencies:
                self._update_package_json(target_dir, dependencies)

            return True

        except Exception as e:
            logger.error(f"템플릿 복사 실패: {e}")
            return False

    def _update_package_json(self, project_dir: Path, additional_dependencies: Dict[str, str]):
        """package.json에 추가 의존성을 업데이트합니다."""
        try:
            package_json_path = project_dir / "package.json"
            
            if not package_json_path.exists():
                logger.warning("package.json 파일을 찾을 수 없습니다")
                return

            # 기존 package.json 읽기
            with open(package_json_path, "r", encoding="utf-8") as f:
                package_data = json.load(f)

            # dependencies 업데이트
            if "dependencies" not in package_data:
                package_data["dependencies"] = {}
            
            package_data["dependencies"].update(additional_dependencies)

            # 업데이트된 package.json 저장
            with open(package_json_path, "w", encoding="utf-8") as f:
                json.dump(package_data, f, indent=2, ensure_ascii=False)

            logger.info(f"package.json 업데이트 완료. 추가된 의존성: {additional_dependencies}")

        except Exception as e:
            logger.error(f"package.json 업데이트 실패: {e}")

    def customize_template(self, target_dir: Path, customizations: Dict[str, Any] = None):
        """
        템플릿을 사용자 정의 설정으로 커스터마이징합니다.
        
        Args:
            target_dir: 프로젝트 디렉토리
            customizations: 커스터마이징 설정
                - app_name: 앱 이름
                - port: 개발 서버 포트
                - title: HTML 제목
        """
        if not customizations:
            return

        try:
            # package.json 이름 변경
            if "app_name" in customizations:
                self._update_app_name(target_dir, customizations["app_name"])

            # vite.config.js 포트 변경
            if "port" in customizations:
                self._update_vite_port(target_dir, customizations["port"])

            # index.html 제목 변경
            if "title" in customizations:
                self._update_html_title(target_dir, customizations["title"])

        except Exception as e:
            logger.error(f"템플릿 커스터마이징 실패: {e}")

    def _update_app_name(self, project_dir: Path, app_name: str):
        """package.json의 앱 이름을 업데이트합니다."""
        package_json_path = project_dir / "package.json"
        
        if package_json_path.exists():
            with open(package_json_path, "r", encoding="utf-8") as f:
                package_data = json.load(f)
            
            package_data["name"] = app_name
            
            with open(package_json_path, "w", encoding="utf-8") as f:
                json.dump(package_data, f, indent=2, ensure_ascii=False)

    def _update_vite_port(self, project_dir: Path, port: int):
        """vite.config.js의 포트를 업데이트합니다."""
        vite_config_path = project_dir / "vite.config.js"
        
        if vite_config_path.exists():
            content = vite_config_path.read_text(encoding="utf-8")
            # 포트 번호 교체
            content = content.replace("port: 3002", f"port: {port}")
            vite_config_path.write_text(content, encoding="utf-8")

    def _update_html_title(self, project_dir: Path, title: str):
        """index.html의 제목을 업데이트합니다."""
        index_html_path = project_dir / "index.html"
        
        if index_html_path.exists():
            content = index_html_path.read_text(encoding="utf-8")
            # 제목 교체
            content = content.replace("<title>Dynamic React App</title>", f"<title>{title}</title>")
            index_html_path.write_text(content, encoding="utf-8")


def get_template_service() -> TemplateService:
    """TemplateService 인스턴스를 생성합니다."""
    from ..core.config import settings
    
    template_dir = Path(__file__).parent.parent.parent / "templates" / "react_boilerplate"
    return TemplateService(template_dir)