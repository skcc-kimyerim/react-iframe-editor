from __future__ import annotations

from typing import Any, Dict

from ..files import resolve_src_path


class FileManagementAgent:
    async def apply_change(self, relative_path: str, content: str, project_name: str = "default-project") -> Dict[str, Any]:
        try:
            file_path = resolve_src_path(relative_path, project_name)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return {"success": True, "path": relative_path}
        except Exception as e:
            return {"success": False, "error": str(e)}

