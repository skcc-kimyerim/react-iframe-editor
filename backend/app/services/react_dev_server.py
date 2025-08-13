import asyncio
import os
import platform
from pathlib import Path
from typing import List, Optional, Set, Dict, Any

from ..core.config import settings


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
                self._process.terminate()
        except ProcessLookupError:
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


react_manager = ReactDevServerManager(settings.REACT_PROJECT_PATH, settings.REACT_DEV_PORT)

