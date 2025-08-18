import asyncio
import os
import platform
import subprocess
from pathlib import Path
from typing import List, Optional, Set, Dict, Any

from ..core.config import settings


# 전역 서버 매니저 - 현재 실행 중인 프로젝트 서버 관리
_current_manager: Optional["ReactDevServerManager"] = None
_current_project_name: Optional[str] = None


class ReactDevServerManager:
    def __init__(self, project_path: Path, port: int) -> None:
        self.project_path = project_path
        self.port = port
        self._process: Optional[asyncio.subprocess.Process] = None
        self._stdout_task: Optional[asyncio.Task] = None
        self._stderr_task: Optional[asyncio.Task] = None
        self._subscribers: Set[asyncio.Queue] = set()
        self._buffer: List[Dict[str, Any]] = []
        self._buffer_limit: int = 500

    def is_running(self) -> bool:
        return self._process is not None and self._process.returncode is None

    async def _run_npm(self, *args: str) -> None:
        npm_command = "npm.cmd" if platform.system() == "Windows" else "npm"
        process = await asyncio.create_subprocess_exec(
            npm_command,
            *args,
            cwd=self.project_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await process.communicate()
        if process.returncode != 0:
            raise RuntimeError(
                f"npm {' '.join(args)} failed with code {process.returncode}: {stderr.decode()}"
            )

    async def install_dependencies(self) -> None:
        await self._run_npm("install")

    async def install_packages(self, packages: List[str]) -> None:
        if not packages:
            return
        await self._run_npm("install", *packages)

    def _project_uses_typescript(self) -> bool:
        src_dir = self.project_path / "src"
        if not src_dir.exists():
            return False
        for root, _, files in os.walk(src_dir):
            for name in files:
                if name.endswith(".ts") or name.endswith(".tsx"):
                    return True
        return False

    def _is_package_installed(self, package_name: str) -> bool:
        return (self.project_path / "node_modules" / package_name / "package.json").exists()
    
    def _is_vite_installed(self) -> bool:
        return (self.project_path / "node_modules" / "vite" / "package.json").exists()

    async def ensure_typescript_and_router(self) -> None:
        needs_ts = self._project_uses_typescript()
        packages_to_install: List[str] = []
        if needs_ts:
            if not self._is_package_installed("typescript"):
                packages_to_install.append("typescript@^5")
            if not self._is_package_installed("@types/react"):
                packages_to_install.append("@types/react@^18")
            if not self._is_package_installed("@types/react-dom"):
                packages_to_install.append("@types/react-dom@^18")
        if not self._is_package_installed("react-router-dom"):
            packages_to_install.append("react-router-dom@^6")
        if packages_to_install:
            await self.install_packages(packages_to_install)

        if needs_ts:
            tsconfig_path = self.project_path / "tsconfig.json"
            if not tsconfig_path.exists():
                import json

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

    async def start(self) -> None:
        if self.is_running():
            return
        vite_installed = self._is_vite_installed()
        if not vite_installed:
            await self.install_dependencies()
        await self.ensure_typescript_and_router()

        npm_command = "npm.cmd" if platform.system() == "Windows" else "npm"
        env = os.environ.copy()
        env.update({
            "BROWSER": "none",
            "CI": "true",
        })

        self._process = await asyncio.create_subprocess_exec(
            npm_command,
            "run",
            "dev",
            cwd=self.project_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

        # spawn readers to capture logs
        if self._process.stdout is not None:
            self._stdout_task = asyncio.create_task(self._read_stream(self._process.stdout, "stdout"))
        if self._process.stderr is not None:
            self._stderr_task = asyncio.create_task(self._read_stream(self._process.stderr, "stderr"))

        # give it some time to boot
        await asyncio.sleep(10)

    async def stop(self) -> None:
        if not self._process:
            return
        try:
            if self._process.returncode is None:
                print(f"🔴 Terminating process PID: {self._process.pid} for project: {self.project_path.name}")
                self._process.terminate()
                # 프로세스가 정말 종료될 때까지 기다림
                try:
                    await asyncio.wait_for(self._process.wait(), timeout=5.0)
                    print(f"✅ Process PID: {self._process.pid} terminated successfully")
                except asyncio.TimeoutError:
                    print(f"⚠️ Process PID: {self._process.pid} did not terminate, force killing...")
                    self._process.kill()
                    await self._process.wait()
                    print(f"💀 Process PID: {self._process.pid} force killed")
        except ProcessLookupError:
            print(f"⚠️ Process already terminated")
            pass
        finally:
            self._process = None
            # cancel readers
            if self._stdout_task:
                self._stdout_task.cancel()
                self._stdout_task = None
            if self._stderr_task:
                self._stderr_task.cancel()
                self._stderr_task = None

    async def _read_stream(self, stream: asyncio.StreamReader, stream_name: str) -> None:
        try:
            while True:
                line = await stream.readline()
                if not line:
                    break
                text = line.decode(errors="replace").rstrip("\n")
                message = {
                    "time": int(asyncio.get_event_loop().time() * 1000),
                    "level": "error" if stream_name == "stderr" else "info",
                    "stream": stream_name,
                    "text": text,
                }
                # buffer
                self._buffer.append(message)
                if len(self._buffer) > self._buffer_limit:
                    self._buffer = self._buffer[-self._buffer_limit :]
                # broadcast
                if self._subscribers:
                    for q in list(self._subscribers):
                        try:
                            q.put_nowait(message)
                        except Exception:
                            pass
        except asyncio.CancelledError:
            return

    def subscribe(self) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subscribers.add(q)
        return q

    def unsubscribe(self, q: asyncio.Queue) -> None:
        try:
            self._subscribers.discard(q)
        except Exception:
            pass

    def get_buffer(self) -> List[Dict[str, Any]]:
        return list(self._buffer)


def _kill_processes_on_port(port: int) -> None:
    """특정 포트를 사용하는 모든 프로세스를 강제 종료"""
    try:
        if platform.system() == "Darwin":  # macOS
            result = subprocess.run(['lsof', '-ti', f':{port}'], capture_output=True, text=True)
            pids = result.stdout.strip().split('\n')
            for pid in pids:
                if pid and pid.isdigit():
                    print(f"💥 Force killing process PID {pid} on port {port}")
                    subprocess.run(['kill', '-9', pid], check=False)
        elif platform.system() == "Linux":
            result = subprocess.run(['fuser', '-k', f'{port}/tcp'], check=False)
    except Exception as e:
        print(f"⚠️ Error killing processes on port {port}: {e}")


async def get_or_create_manager(project_name: str, project_path: Path, port: int) -> ReactDevServerManager:
    """전역 매니저를 통한 프로젝트별 서버 관리"""
    global _current_manager, _current_project_name
    
    print(f"🔄 get_or_create_manager called for project: {project_name}")
    print(f"📊 Current manager: {_current_project_name}, is_running: {_current_manager.is_running() if _current_manager else False}")
    
    # 먼저 포트에서 실행 중인 모든 프로세스 강제 종료
    print(f"🧹 Cleaning up port {port} before starting {project_name}")
    _kill_processes_on_port(port)
    await asyncio.sleep(1)  # 프로세스 종료 대기
    
    # 현재 실행 중인 서버가 다른 프로젝트면 먼저 중지
    if _current_manager and _current_project_name != project_name:
        print(f"🔄 Switching from {_current_project_name} to {project_name}")
        if _current_manager.is_running():
            print(f"🛑 Stopping current manager for {_current_project_name}")
            await _current_manager.stop()
        _current_manager = None
        _current_project_name = None
    
    # 현재 프로젝트의 매니저가 없거나 중지된 상태면 새로 생성
    if not _current_manager or not _current_manager.is_running():
        print(f"🆕 Creating new manager for {project_name}")
        _current_manager = ReactDevServerManager(project_path, port)
        _current_project_name = project_name
    
    return _current_manager


async def stop_current_manager() -> bool:
    """현재 실행 중인 서버 중지"""
    global _current_manager, _current_project_name
    
    print(f"🛑 stop_current_manager called. Current: {_current_project_name}")
    print(f"📊 Manager exists: {_current_manager is not None}, is_running: {_current_manager.is_running() if _current_manager else False}")
    
    if _current_manager:
        if _current_manager.is_running():
            print(f"🔴 Stopping manager for {_current_project_name}")
            await _current_manager.stop()
        else:
            print(f"⚠️ Manager for {_current_project_name} is not running")
        
        _current_manager = None
        _current_project_name = None
        print(f"✅ Global manager reset")
        return True
    else:
        print(f"❌ No current manager to stop")
        return False


def get_current_project_name() -> Optional[str]:
    """현재 실행 중인 프로젝트 이름 반환"""
    return _current_project_name



# 기본 React 관리자 (하위 호환성)
react_manager = ReactDevServerManager(settings.REACT_PROJECT_PATH, settings.REACT_DEV_PORT)

