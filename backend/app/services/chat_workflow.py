from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any, Dict, List, Optional, TypedDict

from langgraph.graph import StateGraph, END

from app.core.config import settings
from .files import resolve_src_path
from .agents import (
    ChatAgent,
    CodeAnalysisAgent,
    CodeGenerationAgent,
    AnalysisGenerationAgent,
    FileManagementAgent,
)
from .agents.utils import _ensure_route_in_app

logger = logging.getLogger("app.chat.workflow")

# 간단 Job 스토어 (메모리)
_JOBS: Dict[str, Dict[str, Any]] = {}


def _new_job(status: str = "queued", message: str = "") -> str:
    job_id = uuid.uuid4().hex
    _JOBS[job_id] = {"status": status, "message": message}
    return job_id


def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    return _JOBS.get(job_id)


class ChatState(TypedDict):
    messages: List[Dict[str, Any]]
    user_input: str
    chat_type: str                 # "general" | "code_analyze" | "code_edit"
    selected_file: Optional[str]
    file_content: Optional[str]
    model: str
    attachments: Optional[List[Dict[str, Any]]]
    project_name: str              # 필수값으로 변경
    result: Dict[str, Any] | None

def _classify(chat_type_hint: Optional[str], user_input: str, selected_file: Optional[str]) -> str:
    if chat_type_hint in {"general", "code_analyze", "code_edit", "code"}:
        return "code_edit" if chat_type_hint == "code" else chat_type_hint

    text = (user_input or "").lower()

    # 파일이 선택된 경우: 기본은 분석, 편집 키워드가 있으면 편집
    if selected_file and str(selected_file).strip():
        edit_keywords = [
            "수정", "변경", "추가", "리팩토링", "고쳐", "fix", "implement", "만들어",
            "만들어줘", "삭제", "리네임", "rename", "적용", "반영", "patch",
        ]
        analyze_keywords = [
            "분석", "읽어", "읽어줘", "설명", "무엇", "뭐하는", "리뷰", "검토",
            "원인", "동작", "어떻게", "어디서", "구조", "의존성", "사용처", "찾아",
        ]
        if any(k in text for k in edit_keywords):
            return "code_edit"
        if any(k in text for k in analyze_keywords):
            return "code_analyze"
        # 명시 키워드가 없으면 안전하게 분석으로
        return "code_analyze"

    # 선택 파일이 없을 때는 코드 관련 키워드가 있으면 편집, 아니면 일반
    code_keywords = [
        "코드", "code", "파일", "file", "컴포넌트", "component",
        "수정", "변경", "추가", "리팩토링", "오류", "에러",
        "import", "export", "props", "state", "hook", "context", "route", "router", "페이지", "page",
    ]
    if any(k in text for k in code_keywords):
        return "code_edit"
    return "general"


def create_graph():
    graph = StateGraph(ChatState)

    async def node_classify(state: ChatState) -> ChatState:
        chat_type = _classify(None, state["user_input"], state.get("selected_file"))
        return {**state, "chat_type": chat_type}

    async def node_general(state: ChatState) -> ChatState:
        
        chat = ChatAgent()
        msg = await chat.reply(
            state["user_input"],
            model=state.get("model"),
            attachments=state.get("attachments") or [],
        )
        return {
            **state,
            "result": {
                "success": True,
                "processing_type": "general",
                "chat_message": msg,
            },
        }

    async def node_code_analyze(state: ChatState) -> ChatState:
        # 파일/코드 분석만 수행. 파일 수정 없음
        project_name = state["project_name"]
        base_projects_dir = settings.REACT_PROJECT_PATH.parent / "projects"
        project_root = str(base_projects_dir / project_name)
        analysis = CodeAnalysisAgent(project_root)
        ctx = analysis.build_context(
            question=state["user_input"],
            selected_file=state.get("selected_file"),
        )

        analyzer = AnalysisGenerationAgent()
        gen = await analyzer.generate_analysis(
            model=state["model"],
            question=state["user_input"],
            selected_file=state.get("selected_file"),
            file_content=state.get("file_content"),
            enhanced_context=ctx.get("enhanced"),
            attachments=state.get("attachments") or [],
        )

        if not gen.get("success"):
            msg = f"분석 생성 실패: {gen.get('message', '원인 불명')}"
        else:
            msg = gen.get("content") or "분석 결과가 비어 있습니다."

        return {
            **state,
            "result": {
                "success": True,
                "processing_type": "code_analyze",
                "chat_message": msg,
            },
        }

    async def node_code_edit(state: ChatState) -> ChatState:
        job_id = _new_job(status="queued", message="대기열에 등록되었습니다.")
        asyncio.create_task(_run_background_job(job_id, state))

        return {
            **state,
            "result": {
                "success": True,
                "processing_type": "code_edit",
                "chat_message": "",
                "job_id": job_id,
            },
        }

    graph.add_node("classify", node_classify)
    graph.add_node("general", node_general)
    graph.add_node("code_analyze", node_code_analyze)
    graph.add_node("code_edit", node_code_edit)

    graph.set_entry_point("classify")
    graph.add_conditional_edges(
        "classify",
        lambda s: s["chat_type"],
        {"general": "general", "code_analyze": "code_analyze", "code_edit": "code_edit"},
    )
    graph.add_edge("general", END)
    graph.add_edge("code_analyze", END)
    graph.add_edge("code_edit", END)

    return graph.compile()


async def _run_background_job(job_id: str, state: ChatState) -> None:
    try:
        _JOBS[job_id]["status"] = "running"
        _JOBS[job_id]["message"] = "코드 분석 중..."

        project_name = state["project_name"]
        base_projects_dir = settings.REACT_PROJECT_PATH.parent / "projects"
        project_root = str(base_projects_dir / project_name)
        analysis = CodeAnalysisAgent(project_root)
        ctx = analysis.build_context(
            question=state["user_input"],
            selected_file=state.get("selected_file"),
        )

        _JOBS[job_id]["message"] = "수정안 생성 중..."
        generator = CodeGenerationAgent()
        gen = await generator.propose_changes(
            model=state["model"],
            question=state["user_input"],
            selected_file=state.get("selected_file"),
            file_content=state.get("file_content"),
            enhanced_context=ctx.get("enhanced"),
            attachments=state.get("attachments") or [],
        )

    
        logger.info(gen)

        if not gen.get("success") or not gen.get("updated_content"):
            _JOBS[job_id]["status"] = "error"
            _JOBS[job_id]["error"] = gen.get("message") or "수정안 생성 실패"
            _JOBS[job_id]["message"] = "작업 실패"
            return

        # LLM이 제공한 변경 설명을 상태에 보관 (코드 블록/경로 제거된 사람용 요약)
        if gen.get("display"):
            _JOBS[job_id]["display"] = gen.get("display")

        target_file = gen.get("file_path") or state.get("selected_file")
        if not target_file:
            _JOBS[job_id]["status"] = "error"
            _JOBS[job_id]["error"] = "대상 파일 경로를 결정할 수 없습니다."
            _JOBS[job_id]["message"] = "작업 실패"
            return

        _JOBS[job_id]["message"] = "파일 적용 중..."
        # 파일 생성 위치 검증: 새 파일일 가능성일 때만 검사 강화
        project_name = state["project_name"]
        is_new_file = target_file and not resolve_src_path(target_file, project_name).exists()
        if is_new_file:
            # 확장자 기반으로 페이지/컴포넌트 추정 없이, 경로 규칙만 강제
            if target_file.startswith("client/pages/"):
                # 라우트 추가 보장 (App.tsx)
                try:
                    _ensure_route_in_app(target_file, project_name)
                except Exception:
                    logger.exception("Route injection encountered an error; continuing")
            elif target_file.startswith("client/components/ui/"):
                pass
            else:
                _JOBS[job_id]["status"] = "error"
                _JOBS[job_id]["error"] = (
                    "새 파일은 client/pages/ 또는 client/components/ui/ 아래에만 생성할 수 있습니다."
                )
                _JOBS[job_id]["message"] = "작업 실패"
                return

        file_mgr = FileManagementAgent()
        applied = await file_mgr.apply_change(target_file, gen["updated_content"], project_name)
        if not applied.get("success"):
            _JOBS[job_id]["status"] = "error"
            _JOBS[job_id]["error"] = applied.get("error", "파일 저장 실패")
            _JOBS[job_id]["message"] = "작업 실패"
            return

        _JOBS[job_id]["status"] = "done"
        _JOBS[job_id]["message"] = "완료"
        _JOBS[job_id]["updatedFile"] = target_file
        _JOBS[job_id]["updatedContent"] = gen["updated_content"]
    except Exception as e:
        logger.exception("Background job failed")
        _JOBS[job_id]["status"] = "error"
        _JOBS[job_id]["error"] = str(e)
        _JOBS[job_id]["message"] = "작업 실패"


class ChatWorkflow:
    def __init__(self):
        self.workflow = create_graph()

    async def process_message(
        self,
        user_message: str,
        messages: List[Dict[str, Any]],
        selected_file: Optional[str] = None,
        file_content: Optional[str] = None,
        model: str = "qwen/qwen3-coder",
        attachments: Optional[List[Dict[str, Any]]] = None,
        project_name: str = "default-project",
    ) -> Dict[str, Any]:
        initial: ChatState = {
            "messages": messages,
            "user_input": user_message,
            "chat_type": "",
            "selected_file": selected_file,
            "file_content": file_content,
            "model": model,
            "attachments": attachments or [],
            "project_name": project_name,
            "result": None,
        }
        final = await self.workflow.ainvoke(initial)
        return final.get("result", {})