from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from pathlib import Path
import json

from ..core.config import settings
from ..services.react_dev_server import react_manager


router = APIRouter(tags=["project"])


class ProjectInitRequest(BaseModel):
    componentCode: str
    dependencies: dict[str, str] = {}


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

        # 프로젝트 디렉터리 생성
        project_path.mkdir(parents=True, exist_ok=True)

        # package.json 생성
        package_json = {
            "name": "dynamic-react-app",
            "version": "0.1.0",
            "private": True,
            "dependencies": {
                "react": "^18.2.0",
                "react-dom": "^18.2.0",
                "react-scripts": "^5.0.1",
                "react-router-dom": "^6.23.0",
                "typescript": "^5.5.0",
                "@types/react": "^18.2.0",
                "@types/react-dom": "^18.2.0",
                **request.dependencies,
            },
            "scripts": {
                "start": "react-scripts start",
                "build": "react-scripts build",
            },
            "eslintConfig": {"extends": ["react-app", "react-app/jest"]},
            "browserslist": {
                "production": [
                    "last 1 Chrome version",
                    "last 1 Firefox version",
                    "last 1 Safari version",
                ],
                "development": [
                    "last 1 Chrome version",
                    "last 1 Firefox version",
                    "last 1 Safari version",
                ],
            },
        }

        with open(project_path / "package.json", "w") as f:
            json.dump(package_json, f, indent=2)

        # src 및 public 디렉토리 생성
        (project_path / "src").mkdir(exist_ok=True)
        (project_path / "public").mkdir(exist_ok=True)

        # App.jsx 생성
        (project_path / "src" / "App.jsx").write_text(request.componentCode, encoding="utf-8")

        # index.js 생성
        index_js = (
            """
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
"""
        ).strip()
        (project_path / "src" / "index.js").write_text(index_js, encoding="utf-8")

        # public/index.html 생성
        index_html = (
            """
<!DOCTYPE html>
<html lang=\"ko\">
<head>
  <meta charset=\"utf-8\" />
  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
  <title>Dynamic React App</title>
  </head>
<body>
  <div id=\"root\"></div>
</body>
</html>
"""
        ).strip()
        (project_path / "public" / "index.html").write_text(index_html, encoding="utf-8")

        # 의존성 설치 및 개발 서버 시작
        await react_manager.install_dependencies()
        await react_manager.ensure_typescript_and_router()
        await react_manager.start()

        dev_server_url = f"http://localhost:{settings.REACT_DEV_PORT}/"
        return {
            "success": True,
            "message": "Project initialized and dev server started",
            "devServerUrl": dev_server_url,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to prepare or initialize project: {e}")

