from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import json
import os
import platform
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Union
import atexit

app = FastAPI()

# CORS 설정
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 설정
PORT = 3001
REACT_PROJECT_PATH = Path(__file__).parent / "dynamic-react-app"
REACT_DEV_PORT = 3002

# 전역 변수
react_dev_server = None

# Request 모델들
class ComponentUpdateRequest(BaseModel):
    content: str

class ProjectInitRequest(BaseModel):
    componentCode: str
    dependencies: Dict[str, str] = {}

class FileSaveRequest(BaseModel):
    relativePath: str
    content: str

# API 엔드포인트들
@app.get("/api/test")
async def test_endpoint():
    return {
        "message": "Backend server is running",
        "timestamp": datetime.now().isoformat()
    }

async def install_dependencies():
    """npm install 실행"""
    print("📦 Installing React dependencies...")
    
    try:
        npm_command = "npm.cmd" if platform.system() == "Windows" else "npm"
        
        process = await asyncio.create_subprocess_exec(
            npm_command, "install",
            cwd=REACT_PROJECT_PATH,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        
        stdout, stderr = await process.communicate()
        
        if process.returncode == 0:
            print("✅ React dependencies installed successfully")
        else:
            print(f"❌ npm install failed with code {process.returncode}")
            print(f"stderr: {stderr.decode()}")
            raise Exception(f"npm install failed with code {process.returncode}")
            
    except Exception as e:
        print(f"❌ npm install error: {e}")
        raise e

async def install_packages(packages: List[str]):
    """특정 패키지 설치 (존재 여부와 무관하게 재시도 가능)"""
    if not packages:
        return
    print(f"📦 Installing packages: {' '.join(packages)}")
    try:
        npm_command = "npm.cmd" if platform.system() == "Windows" else "npm"
        process = await asyncio.create_subprocess_exec(
            npm_command, "install", *packages,
            cwd=REACT_PROJECT_PATH,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode == 0:
            print("✅ Packages installed successfully")
        else:
            print(f"❌ npm install failed with code {process.returncode}")
            print(f"stderr: {stderr.decode()}")
            raise Exception(f"npm install failed with code {process.returncode}")
    except Exception as e:
        print(f"❌ npm install error: {e}")
        raise e

def project_uses_typescript() -> bool:
    """src 디렉토리에 .ts 또는 .tsx 파일이 있는지 검사"""
    src_dir = REACT_PROJECT_PATH / "src"
    if not src_dir.exists():
        return False
    for root, _, files in os.walk(src_dir):
        for name in files:
            if name.endswith(".ts") or name.endswith(".tsx"):
                return True
    return False

def is_package_installed(package_name: str) -> bool:
    path = REACT_PROJECT_PATH / "node_modules" / package_name / "package.json"
    return path.exists()

async def ensure_typescript_and_router():
    """TypeScript 사용 시 필요한 패키지와 tsconfig 보장, 라우터도 보장"""
    needs_ts = project_uses_typescript()
    packages_to_install: List[str] = []
    if needs_ts:
        if not is_package_installed("typescript"):
            packages_to_install.append("typescript@^5")
        if not is_package_installed("@types/react"):
            packages_to_install.append("@types/react@^18")
        if not is_package_installed("@types/react-dom"):
            packages_to_install.append("@types/react-dom@^18")
    # 라우터 사용 여부는 가볍게 항상 보장
    if not is_package_installed("react-router-dom"):
        packages_to_install.append("react-router-dom@^6")

    if packages_to_install:
        await install_packages(packages_to_install)

    # tsconfig.json 생성 보장 (TypeScript 사용 시)
    if needs_ts:
        tsconfig_path = REACT_PROJECT_PATH / "tsconfig.json"
        if not tsconfig_path.exists():
            tsconfig = {
                "compilerOptions": {
                    "target": "ES2020",
                    "lib": ["DOM", "ES2020"],
                    "jsx": "react-jsx",
                    "module": "ESNext",
                    "moduleResolution": "Node",
                    "skipLibCheck": True,
                    "esModuleInterop": True,
                    "forceConsistentCasingInFileNames": True,
                    "strict": False,
                    "noEmit": True,
                },
                "include": ["src"],
            }
            tsconfig_path.write_text(json.dumps(tsconfig, indent=2), encoding="utf-8")

async def check_react_scripts_installed():
    """react-scripts 설치 확인"""
    try:
        package_path = REACT_PROJECT_PATH / "node_modules" / "react-scripts" / "package.json"
        if package_path.exists():
            print("✅ react-scripts is installed")
            return True
        else:
            print("❌ react-scripts not found")
            return False
    except Exception:
        print("❌ react-scripts not found")
        return False

async def start_react_dev_server():
    """React 개발 서버 시작"""
    global react_dev_server
    
    if react_dev_server:
        return
    
    scripts_installed = await check_react_scripts_installed()
    if not scripts_installed:
        print("⚠️ react-scripts not found, installing dependencies first...")
        await install_dependencies()
    # TypeScript/Router 보장
    await ensure_typescript_and_router()
    
    print("Starting React dev server...")
    
    npm_command = "npm.cmd" if platform.system() == "Windows" else "npm"
    
    env = os.environ.copy()
    env.update({
        "PORT": str(REACT_DEV_PORT),
        "BROWSER": "none",
        "CI": "true"
    })
    
    react_dev_server = await asyncio.create_subprocess_exec(
        npm_command, "start",
        cwd=REACT_PROJECT_PATH,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
        env=env
    )
    
    # 비동기적으로 출력 모니터링
    asyncio.create_task(monitor_react_server_output())
    
    # 서버 시작 대기
    await asyncio.sleep(10)

async def monitor_react_server_output():
    """React 서버 출력 모니터링"""
    global react_dev_server
    
    if not react_dev_server:
        return
    
    try:
        while react_dev_server.returncode is None:
            line = await react_dev_server.stdout.readline()
            if line:
                output = line.decode().strip()
                print(f"React Dev: {output}")
                
                if "webpack compiled" in output or "Compiled successfully" in output:
                    print("✅ React dev server is ready")
            else:
                break
    except Exception as e:
        print(f"Error monitoring React server: {e}")

def stop_react_dev_server():
    """React 개발 서버 중지"""
    global react_dev_server
    
    if not react_dev_server:
        return
    try:
        # 프로세스가 여전히 실행 중인 경우에만 종료 시도
        if react_dev_server.returncode is None:
            react_dev_server.terminate()
    except ProcessLookupError:
        # 이미 종료된 프로세스인 경우 무시
        pass
    except Exception as e:
        # 예외는 로깅하고 무시하여 API가 500을 반환하지 않도록 함
        print(f"Error stopping dev server process: {e}")
    finally:
        react_dev_server = None

@app.get("/api/files")
async def get_files():
    """프로젝트 루트의 파일 트리 조회 (node_modules 제외)"""
    base_dir = REACT_PROJECT_PATH
    print(base_dir)
    if not base_dir.exists():
        return {"tree": []}
    try:
        tree = build_file_tree(base_dir, "")
        return {"tree": tree}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file tree: {str(e)}")


@app.get("/api/file")
async def read_file(relativePath: str):  # camelCase는 프론트 요청과 일치
    try:
        file_path = resolve_src_path(relativePath)
        if not file_path.exists() or not file_path.is_file():
            raise HTTPException(status_code=404, detail="File not found")
        content = file_path.read_text(encoding="utf-8")
        return {"content": content}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read file: {str(e)}")


@app.put("/api/file")
async def save_file(payload: FileSaveRequest):
    try:
        file_path = resolve_src_path(payload.relativePath)
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(payload.content, encoding="utf-8")
        return {"success": True, "message": "File saved successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
# 안전한 프로젝트 루트 경로 해석
def resolve_src_path(relative_path: str) -> Path:
    if not relative_path or not isinstance(relative_path, str):
        raise HTTPException(status_code=400, detail="Invalid relativePath")
    normalized = os.path.normpath(relative_path).lstrip(os.sep)
    project_base = REACT_PROJECT_PATH
    resolved = project_base / normalized
    try:
        resolved.relative_to(project_base)
    except ValueError:
        raise HTTPException(status_code=400, detail="Path traversal detected")
    return resolved


def build_file_tree(dir_path: Path, base_relative: str = "") -> List[Dict[str, Union[str, list]]]:
    if not dir_path.exists():
        return []
    nodes: List[Dict[str, Union[str, list]]] = []
    # 디렉토리 우선, 이름순 정렬
    for entry in sorted(dir_path.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
        # node_modules는 트리에서 제외
        if entry.is_dir() and entry.name == "node_modules":
            continue
        rel_path = os.path.join(base_relative, entry.name) if base_relative else entry.name
        if entry.is_dir():
            children = build_file_tree(entry, rel_path)
            nodes.append({
                "type": "directory",
                "name": entry.name,
                "path": rel_path,
                "children": children,
            })
        else:
            nodes.append({
                "type": "file",
                "name": entry.name,
                "path": rel_path,
            })
    return nodes

@app.put("/api/component/{filename}")
async def update_component(filename: str, request: ComponentUpdateRequest):
    """컴포넌트 업데이트"""
    try:
        file_path = REACT_PROJECT_PATH / "src" / filename
        
        print(f"📝 Updating component: {filename}")
        
        # 디렉토리가 존재하지 않으면 생성
        file_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(request.content)
        
        print(f"✅ Updated component: {filename}")
        
        return {"success": True, "message": "Component updated successfully"}
        
    except Exception as e:
        print(f"❌ Error updating component: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to update component: {str(e)}")

@app.post("/api/init-project")
async def init_project(request: ProjectInitRequest):
    """동작: 프로젝트가 존재하면 실행만, 없으면 초기화 후 실행"""
    try:
        print("📦 Preparing project...")

        # 1) 기존 프로젝트가 있으면 초기화하지 않고 바로 개발 서버 실행
        if REACT_PROJECT_PATH.exists():
            print("📁 Existing project detected. Starting dev server...")
            await start_react_dev_server()
            dev_server_url = f"http://localhost:{REACT_DEV_PORT}/"
            return {
                "success": True,
                "message": "Existing project detected. Dev server started",
                "devServerUrl": dev_server_url,
            }

        # 2) 없으면 프로젝트 초기화
        print("🆕 No project found. Initializing new project...")

        # React 프로젝트 디렉토리 생성
        REACT_PROJECT_PATH.mkdir(parents=True, exist_ok=True)

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

        with open(REACT_PROJECT_PATH / "package.json", "w") as f:
            json.dump(package_json, f, indent=2)

        # src 및 public 디렉토리 생성
        (REACT_PROJECT_PATH / "src").mkdir(exist_ok=True)
        (REACT_PROJECT_PATH / "public").mkdir(exist_ok=True)

        # App.jsx 생성 (요청 코드가 JS/TS 상관없이 JSX로 저장)
        with open(REACT_PROJECT_PATH / "src" / "App.jsx", "w", encoding="utf-8") as f:
            f.write(request.componentCode)

        # index.js 생성
        index_js = """
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
"""

        with open(REACT_PROJECT_PATH / "src" / "index.js", "w") as f:
            f.write(index_js)

        # public/index.html 생성
        index_html = """
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Dynamic React App</title>
</head>
<body>
  <div id="root"></div>
</body>
</html>
"""

        with open(REACT_PROJECT_PATH / "public" / "index.html", "w") as f:
            f.write(index_html)

        # 의존성 설치 후 추가 의존성 보장
        await install_dependencies()
        await ensure_typescript_and_router()
        await start_react_dev_server()

        dev_server_url = f"http://localhost:{REACT_DEV_PORT}/"
        print("✅ Project initialized and dev server started successfully")
        return {
            "success": True,
            "message": "Project initialized and dev server started",
            "devServerUrl": dev_server_url,
        }

    except Exception as e:
        print(f"❌ Error preparing/initializing project: {e}")
        raise HTTPException(status_code=500, detail="Failed to prepare or initialize project")

@app.post("/api/start-dev-server")
async def start_dev_server():
    """React 개발 서버 시작"""
    try:
        print("🚀 Attempting to start React dev server...")
        
        # 프로젝트 존재 확인
        if not REACT_PROJECT_PATH.exists():
            raise HTTPException(status_code=400, detail="React project not initialized. Please initialize first.")
        
        await start_react_dev_server()
        
        dev_server_url = f"http://localhost:{REACT_DEV_PORT}/"
        print(f"✅ React dev server started at {dev_server_url}")
        
        return {
            "success": True,
            "devServerUrl": dev_server_url,
            "message": "React dev server started successfully"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"❌ Error starting dev server: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start dev server: {str(e)}")

@app.post("/api/stop-dev-server")
async def stop_dev_server():
    """React 개발 서버 중지"""
    stop_react_dev_server()
    return {"success": True, "message": "React dev server stopped"}

# 애플리케이션 종료 시 정리
atexit.register(stop_react_dev_server)

if __name__ == "__main__":
    import uvicorn
    print(f"🚀 Backend server running on http://localhost:{PORT}")
    print(f"📡 API endpoints available at http://localhost:{PORT}/api/")
    uvicorn.run("main:app", host="0.0.0.0", port=PORT, reload=True)