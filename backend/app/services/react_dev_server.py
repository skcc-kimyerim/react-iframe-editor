import asyncio
import os
import platform
from pathlib import Path
from typing import List, Optional

from ..core.config import settings


class ReactDevServerManager:
    def __init__(self, project_path: Path, port: int) -> None:
        self.project_path = project_path
        self.port = port
        self._process: Optional[asyncio.subprocess.Process] = None

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
        scripts_installed = (self.project_path / "node_modules" / "react-scripts" / "package.json").exists()
        if not scripts_installed:
            await self.install_dependencies()
        await self.ensure_typescript_and_router()

        npm_command = "npm.cmd" if platform.system() == "Windows" else "npm"
        env = os.environ.copy()
        env.update({
            "PORT": str(self.port),
            "BROWSER": "none",
            "CI": "true",
        })

        self._process = await asyncio.create_subprocess_exec(
            npm_command,
            "start",
            cwd=self.project_path,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=env,
        )

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


react_manager = ReactDevServerManager(settings.REACT_PROJECT_PATH, settings.REACT_DEV_PORT)

