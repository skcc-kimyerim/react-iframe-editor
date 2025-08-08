from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import asyncio
import subprocess
import json
import os
import shutil
import platform
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

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
    
    if react_dev_server:
        react_dev_server.terminate()
        react_dev_server = None

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
    """React 프로젝트 초기화"""
    try:
        print("📦 Initializing project...")
        
        # 기존 프로젝트 제거
        if REACT_PROJECT_PATH.exists():
            print("🗑️ Removing existing project...")
            shutil.rmtree(REACT_PROJECT_PATH)
        
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
                **request.dependencies
            },
            "scripts": {
                "start": "react-scripts start",
                "build": "react-scripts build"
            },
            "eslintConfig": {
                "extends": ["react-app", "react-app/jest"]
            },
            "browserslist": {
                "production": ["last 1 Chrome version", "last 1 Firefox version", "last 1 Safari version"],
                "development": ["last 1 Chrome version", "last 1 Firefox version", "last 1 Safari version"]
            }
        }
        
        with open(REACT_PROJECT_PATH / "package.json", 'w') as f:
            json.dump(package_json, f, indent=2)
        
        # src 및 public 디렉토리 생성
        (REACT_PROJECT_PATH / "src").mkdir(exist_ok=True)
        (REACT_PROJECT_PATH / "public").mkdir(exist_ok=True)
        
        # App.js 생성
        with open(REACT_PROJECT_PATH / "src" / "App.js", 'w', encoding='utf-8') as f:
            f.write(request.componentCode)
        
        # index.js 생성
        index_js = """
import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';

const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(<App />);
"""
        
        with open(REACT_PROJECT_PATH / "src" / "index.js", 'w') as f:
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
        
        with open(REACT_PROJECT_PATH / "public" / "index.html", 'w') as f:
            f.write(index_html)
        
        # 의존성 설치
        await install_dependencies()
        
        print("✅ Project initialized successfully")
        return {"success": True, "message": "Project initialized successfully"}
        
    except Exception as e:
        print(f"❌ Error initializing project: {e}")
        raise HTTPException(status_code=500, detail="Failed to initialize project")

@app.post("/api/start-dev-server")
async def start_dev_server():
    """React 개발 서버 시작"""
    try:
        print("🚀 Attempting to start React dev server...")
        
        # 프로젝트 존재 확인
        if not REACT_PROJECT_PATH.exists():
            raise HTTPException(status_code=400, detail="React project not initialized. Please initialize first.")
        
        await start_react_dev_server()
        
        dev_server_url = f"http://localhost:{REACT_DEV_PORT}"
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
import atexit
atexit.register(stop_react_dev_server)

if __name__ == "__main__":
    import uvicorn
    print(f"🚀 Backend server running on http://localhost:{PORT}")
    print(f"📡 API endpoints available at http://localhost:{PORT}/api/")
    uvicorn.run(app, host="0.0.0.0", port=PORT)