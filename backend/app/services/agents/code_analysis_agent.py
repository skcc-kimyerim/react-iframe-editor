from __future__ import annotations

from typing import Any, Dict, Optional

from ..file_analyzer import FileAnalyzer
from ..context_builder import ContextBuilder


class CodeAnalysisAgent:
    def __init__(self, project_root: str):
        self.project_root = project_root
        self._file_analyzer = FileAnalyzer(project_root)
        self._context_builder = ContextBuilder(self._file_analyzer)

    def build_context(self, question: str, selected_file: Optional[str]) -> Dict[str, Any]:
        _ = self._file_analyzer.analyze_project_structure("client")
        context_info = self._context_builder.build_context_for_question(
            question=question, selected_file=selected_file
        )
        enhanced = self._context_builder.create_optimized_context(
            question=question, selected_file=selected_file
        )
        return {"info": context_info, "enhanced": enhanced}

