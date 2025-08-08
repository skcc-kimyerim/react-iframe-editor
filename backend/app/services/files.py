import os
from pathlib import Path
from typing import Dict, List, Union

from fastapi import HTTPException
from ..core.config import settings


def resolve_src_path(relative_path: str) -> Path:
    if not relative_path or not isinstance(relative_path, str):
        raise HTTPException(status_code=400, detail="Invalid relativePath")
    normalized = os.path.normpath(relative_path).lstrip(os.sep)
    project_base = settings.REACT_PROJECT_PATH
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
    for entry in sorted(dir_path.iterdir(), key=lambda p: (p.is_file(), p.name.lower())):
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

