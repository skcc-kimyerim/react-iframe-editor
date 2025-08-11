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
            "type": "module",
            "dependencies": {
                "react": "^18.2.0",
                "react-dom": "^18.2.0",
                "react-router-dom": "^6.23.0",
                **request.dependencies,
            },
            "devDependencies": {
                "@types/react": "^18.2.0",
                "@types/react-dom": "^18.2.0",
                "@vitejs/plugin-react": "^4.2.1",
                "typescript": "^5.5.0",
                "vite": "^5.1.4",
                "tailwindcss": "^3.4.17",
                "autoprefixer": "^10.4.21",
                "postcss": "^8.5.6"
            },
            "scripts": {
                "dev": "vite",
                "build": "vite build",
                "preview": "vite preview"
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
        (project_path / "src" / "pages").mkdir(exist_ok=True)
        (project_path / "public").mkdir(exist_ok=True)

        # App.tsx 생성 - 기본 템플릿이 없으면 React Router 예시 코드 사용
        app_code = request.componentCode if request.componentCode.strip() else """import { BrowserRouter, Routes, Route } from 'react-router-dom'
import Home from './pages/Home'

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home />} />
      </Routes>
    </BrowserRouter>
  )
}

export default App"""
        
        (project_path / "src" / "App.tsx").write_text(app_code, encoding="utf-8")

        # src/pages/Home.tsx 생성
        home_tsx = """
function Home() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center">
      <div className="max-w-md mx-auto text-center">
        <h1 className="text-4xl font-bold text-gray-900 mb-4">환영합니다!</h1>
        <p className="text-gray-600 mb-8">React Router가 설정된 동적 React 앱입니다.</p>
        <div className="space-y-4">
          <p className="text-sm text-gray-500">
            새로운 페이지를 만들어 라우팅을 확장해보세요!
          </p>
        </div>
      </div>
    </div>
  )
}

export default Home"""
        
        (project_path / "src" / "pages" / "Home.tsx").write_text(home_tsx, encoding="utf-8")

        # main.tsx 생성 (Vite는 main.tsx 사용)
        main_tsx = """import React from 'react'
import ReactDOM from 'react-dom/client'
import './index.css'
import App from './App'

ReactDOM.createRoot(document.getElementById('root')).render(
    <App />
)"""
        (project_path / "src" / "main.tsx").write_text(main_tsx, encoding="utf-8")

        # index.html 생성 (Vite는 루트에 위치)
        index_html = """<!DOCTYPE html>
<html lang="ko">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/vite.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Dynamic React App</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>"""
        (project_path / "index.html").write_text(index_html, encoding="utf-8")

        # vite.config.js 생성
        vite_config = """import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3002,
    host: true
  }
})"""
        (project_path / "vite.config.js").write_text(vite_config, encoding="utf-8")

        # tailwind.config.js 생성
        tailwind_config = """/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {},
  },
  plugins: [],
}"""
        (project_path / "tailwind.config.js").write_text(tailwind_config, encoding="utf-8")

        # postcss.config.js 생성
        postcss_config = """export default {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}"""
        (project_path / "postcss.config.js").write_text(postcss_config, encoding="utf-8")

        # src/index.css 생성 (Tailwind CSS imports 포함)
        index_css = """@tailwind base;
@tailwind components;
@tailwind utilities;

body {
  margin: 0;
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", "Roboto", "Oxygen",
    "Ubuntu", "Cantarell", "Fira Sans", "Droid Sans", "Helvetica Neue",
    sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}"""
        (project_path / "src" / "index.css").write_text(index_css, encoding="utf-8")

        print(project_path)
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

