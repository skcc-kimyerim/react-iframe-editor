from __future__ import annotations

import asyncio
import logging
import re
import uuid
from typing import Any, Dict, List, Optional, TypedDict

import httpx
from langgraph.graph import StateGraph, END

from app.core.config import settings
from .file_analyzer import FileAnalyzer
from .context_builder import ContextBuilder
from .files import resolve_src_path

logger = logging.getLogger("app.chat.workflow")

# 간단 Job 스토어 (메모리)
_JOBS: Dict[str, Dict[str, Any]] = {}


def _new_job(status: str = "queued", message: str = "") -> str:
    job_id = uuid.uuid4().hex
    _JOBS[job_id] = {"status": status, "message": message}
    return job_id


def get_job_status(job_id: str) -> Optional[Dict[str, Any]]:
    return _JOBS.get(job_id)


# -------- Utilities --------
def _to_pascal_case(name: str) -> str:
    parts = re.split(r"[^A-Za-z0-9]+", name)
    return "".join(p.capitalize() for p in parts if p)


def _to_kebab_case(name: str) -> str:
    # Convert PascalCase or camelCase to kebab-case
    s1 = re.sub(r"([a-z0-9])([A-Z])", r"\1-\2", name)
    s2 = re.sub(r"[^A-Za-z0-9]+", "-", s1)
    return s2.strip('-').lower()


def _ensure_route_in_app(page_relative_path: str) -> None:
    try:
        app_path = resolve_src_path("client/App.tsx")
        if not app_path.exists():
            logger.warning("App.tsx not found; skipping route injection")
            return

        try:
            text = app_path.read_text(encoding="utf-8")
        except Exception:
            logger.exception("Failed to read App.tsx")
            return

        # Derive component name and import path
        # Expecting page_relative_path like "client/pages/MyPage.tsx"
        filename = page_relative_path.split("/")[-1]
        base, ext = (filename.rsplit(".", 1) + [""])[:2]
        component = _to_pascal_case(base)
        import_stmt = f'import {component} from "./pages/{component}";'

        # Insert import if missing
        if import_stmt not in text:
            lines = text.splitlines()
            last_import_idx = -1
            for idx, line in enumerate(lines):
                if line.strip().startswith("import "):
                    last_import_idx = idx
            insert_at = last_import_idx + 1 if last_import_idx >= 0 else 0
            lines.insert(insert_at, import_stmt)
            text = "\n".join(lines)

        # Insert Route before catch-all or after root route
        route_line = f'          <Route path="/{_to_kebab_case(component)}" element={{<{component} />}} />'
        if route_line not in text:
            if "<Routes>" in text and "path=\"*\"" in text:
                text = re.sub(
                    r"(\s*<Route\s+path=\"\*\"[\s\S]*?>\s*</Route>|\s*<Route\s+path=\"\*\"[\s\S]*/>\s*)",
                    route_line + "\n" + r"\1",
                    text,
                    count=1,
                )
            elif "<Routes>" in text:
                text = text.replace("<Routes>", "<Routes>\n" + route_line)

        try:
            app_path.write_text(text, encoding="utf-8")
        except Exception:
            logger.exception("Failed to write App.tsx with new route")
    except Exception:
        logger.exception("Route injection failed")


class ChatState(TypedDict):
    messages: List[Dict[str, Any]]
    user_input: str
    chat_type: str                 # "general" | "code_analyze" | "code_edit"
    selected_file: Optional[str]
    file_content: Optional[str]
    model: str
    result: Dict[str, Any] | None


# -------- Agents --------
class ChatAgent:
    async def reply(self, user_input: str, model: Optional[str] = None) -> str:
        """
        일반 대화 응답을 생성합니다.
        - OPENROUTER_API_KEY가 있으면 OpenRouter로 충분하고 구체적인 한국어 답변을 생성
        - 없거나 실패 시, 오류 메시지를 간단히 반환
        """
        api_key = settings.OPENROUTER_API_KEY
        if not api_key:
            return "OPENROUTER_API_KEY가 없습니다."

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": f"http://localhost:{settings.PORT}",
                "X-Title": "React Iframe Editor - Quick Reply",
            }
            system = (
                "다음 사용자 요청에 대해 한국어로 명확하고 충분한 답변을 제공하세요. "
                "불필요한 사족은 줄이고, 필요한 경우 목록이나 간단한 코드/예시를 포함해 실용적으로 답하세요."
            )
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user_input},
            ]
            payload = {
                "model": model or "qwen/qwen3-coder",
                "messages": messages,
                "stream": False,
                "temperature": 0.1,
            }

            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )
                if r.status_code != 200:
                    logger.warning("Quick reply OpenRouter error: %s", r.text)
                    return f"OpenRouter 요청 실패: {r.text}"

                data = r.json()
                content = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip()
                )
                return content or "요청을 확인했습니다. 관련 코드를 점검하고 필요한 수정을 백그라운드에서 진행할게요."
        except Exception as e:
            logger.exception("Quick reply generation failed")
            return f"OpenRouter 요청 실패: {e}"


class CodeAnalysisAgent:
    def __init__(self, project_root: str):
        self.project_root = project_root
        self._file_analyzer = FileAnalyzer(project_root)
        self._context_builder = ContextBuilder(self._file_analyzer)

    def build_context(self, question: str, selected_file: Optional[str]) -> Dict[str, Any]:
        # 초기 전체 구조(캐시) 구축
        _ = self._file_analyzer.analyze_project_structure("client")
        context_info = self._context_builder.build_context_for_question(
            question=question, selected_file=selected_file
        )
        enhanced = self._context_builder.create_optimized_context(
            question=question, selected_file=selected_file
        )
        return {"info": context_info, "enhanced": enhanced}


class CodeGenerationAgent:
    async def propose_changes(
        self,
        model: str,
        question: str,
        selected_file: Optional[str],
        file_content: Optional[str],
        enhanced_context: Optional[str],
    ) -> Dict[str, Any]:
        """
        OpenRouter 호출로 코드 수정 제안 생성.
        - FILEPATH 또는 코드 펜스 헤더(path|file|filename|title=...)로 대상 파일 유추
        - 코드 블록 안에 전체 변경본 제공
        """
        api_key = settings.OPENROUTER_API_KEY
        if not api_key:
            return {"success": False, "message": "OPENROUTER_API_KEY not configured"}

        system = "당신은 React/TypeScript 코드 전문가입니다."
        if selected_file and file_content is not None:
            system += f"""
        현재 선택된 파일: {selected_file}
        현재 파일 내용:{file_content}
"""
        if enhanced_context:
            system += f"""

프로젝트 컨텍스트:
{enhanced_context}

위 컨텍스트를 참고하여 관련 파일 간의 관계, 코드 스타일, 폴더 구조를 고려해서 답변하세요."""

        system += """
사용자의 요청에 따라 코드를 수정해야 하는 경우:
1) 먼저 수정 내용에 대한 간단한 설명
2) 수정된 전체 코드를 하나의 코드 블록(```typescript/```javascript/```tsx/```jsx)에 포함
3) 새 파일 생성 시 코드 블록 바로 위에 'FILEPATH: client/경로/파일명' 한 줄을 정확히 추가
   - 코드 펜스 헤더에 path=..., file=..., filename=..., title=... 도 허용 (예: ```tsx title=client/pages/Home.tsx)
   - 기존 파일 수정 시 FILEPATH 생략
설명은 간단하고 명확하게."""

        # 파일 생성 위치 규칙
        system += """

[중요: 새 파일 생성 위치 규칙]
- 새 페이지 파일은 반드시 client/pages/ 아래에 생성하세요.
- 새로 생성된 페이지는 반드시 App.tsx에 추가되어야 합니다.
- 새 컴포넌트 파일은 반드시 client/components/ui/ 아래에 생성하세요.
- 다른 위치에 새 파일을 만들지 마세요.
\n[파일명 규칙]
- 페이지 파일명은 반드시 PascalCase를 사용하세요 (예: AboutUs.tsx).
"""

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ]

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": f"http://localhost:{settings.PORT}",
            "X-Title": "React Iframe Editor - Agents",
        }

        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
            if r.status_code != 200:
                return {"success": False, "message": f"API error: {r.text}"}

            data = r.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""

        # 경로 추출
        file_path = None
        header_path_match = re.search(
            r'```(?:typescript|javascript|tsx|jsx)[^\n]*?(?:path|file(?:name)?|title)\s*[:=]\s*([^\s\n`]+)',
            content,
            re.IGNORECASE,
        )
        if header_path_match:
            file_path = header_path_match.group(1).strip().strip('"').strip("'")

        if not file_path:
            directive_match = re.search(r'(?im)^\s*(?:FILEPATH|FILE|FILENAME|PATH)\s*[:=]\s*(.+)$', content)
            if directive_match:
                file_path = directive_match.group(1).strip()

        if file_path:
            normalized_path = file_path.strip()
            if normalized_path.startswith("./"):
                normalized_path = normalized_path[2:]
            normalized_path = normalized_path.lstrip("/")
            if normalized_path.startswith("src/client/"):
                normalized_path = normalized_path[len("src/"):]
            elif normalized_path.startswith("src/"):
                normalized_path = "client/" + normalized_path[len("src/"):]
            # pages, components 최상위 경로 보정
            if normalized_path.startswith("pages/"):
                normalized_path = "client/pages/" + normalized_path[len("pages/"):]
            if normalized_path.startswith("components/") and not normalized_path.startswith("components/ui/"):
                normalized_path = "client/components/ui/" + normalized_path[len("components/"):]

            # 페이지 이름은 PascalCase 강제
            if normalized_path.startswith("client/pages/"):
                parts = normalized_path.split("/")
                filename = parts[-1]
                if "." in filename:
                    base, ext = filename.rsplit(".", 1)
                    pascal = _to_pascal_case(base)
                    if base != pascal:
                        parts[-1] = f"{pascal}.{ext}"
                        normalized_path = "/".join(parts)
                else:
                    pascal = _to_pascal_case(filename)
                    if filename != pascal:
                        parts[-1] = pascal
                        normalized_path = "/".join(parts)
            file_path = normalized_path

        # 코드 블록 추출
        code_blocks = re.findall(r'```(?:typescript|javascript|tsx|jsx)\n(.*?)\n```', content, re.DOTALL)
        updated_content = code_blocks[0].strip() if code_blocks else None

        # 채팅 표시는 코드/FILEPATH 제거
        display = content
        if code_blocks:
            display = re.sub(r'```(?:typescript|javascript|tsx|jsx)\n.*?\n```', '', display, flags=re.DOTALL)
            display = re.sub(r'(?im)^\s*(?:FILEPATH|FILE|FILENAME|PATH)\s*[:=].+$', '', display)
            display = display.strip()
            if len(display) < 10:
                display = "코드 수정안을 생성했습니다. 백그라운드에서 적용 중입니다."

        return {
            "success": True,
            "display": display,
            "file_path": file_path,
            "updated_content": updated_content,
        }


class AnalysisGenerationAgent:
    async def generate_analysis(
        self,
        model: str,
        question: str,
        selected_file: Optional[str],
        file_content: Optional[str],
        enhanced_context: Optional[str],
    ) -> Dict[str, Any]:
        api_key = settings.OPENROUTER_API_KEY
        if not api_key:
            return {"success": False, "message": "OPENROUTER_API_KEY not configured"}

        system = (
            "당신은 React/TypeScript 코드 분석가입니다. 사용자의 질문과 선택된 파일, "
            "그리고 프로젝트 컨텍스트를 바탕으로 한국어로 명확한 분석 리포트를 작성하세요.\n"
            "- 요약\n- 파일 개요(역할, 주요 export/컴포넌트)\n- 중요한 상태/함수/로직\n"
            "- 의존성 및 사용처(연관 파일/컴포넌트)\n- 잠재 이슈 및 개선 제안\n"
            "코드 수정본이나 FILEPATH 지시문, 코드 펜스는 포함하지 마세요. 필요 시 짧은 코드 조각만 인라인로 인용하세요."
        )
        if selected_file and file_content is not None:
            system += f"""

선택된 파일: {selected_file}
현재 파일 내용:
{file_content}
"""
        if enhanced_context:
            system += f"""

프로젝트 컨텍스트:
{enhanced_context}
"""

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": question or "해당 파일을 분석해줘"},
        ]

        payload = {"model": model, "messages": messages, "stream": False, "temperature": 0.2}
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": f"http://localhost:{settings.PORT}",
            "X-Title": "React Iframe Editor - Analysis",
        }

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
                if r.status_code != 200:
                    return {"success": False, "message": f"API error: {r.text}"}
                data = r.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
                return {"success": True, "content": content.strip()}
        except Exception as e:
            logger.exception("Analysis generation failed")
            return {"success": False, "message": str(e)}


class FileManagementAgent:
    async def apply_change(self, relative_path: str, content: str) -> Dict[str, Any]:
        try:
            file_path = resolve_src_path(relative_path)
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return {"success": True, "path": relative_path}
        except Exception as e:
            return {"success": False, "error": str(e)}


# -------- LangGraph --------
def _classify(chat_type_hint: Optional[str], user_input: str, selected_file: Optional[str]) -> str:
    # 힌트가 오면 최대한 존중 (하위호환: "code"는 편집으로 간주)
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
        msg = await chat.reply(state["user_input"], model=state.get("model"))
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
        project_root = str(settings.REACT_PROJECT_PATH)
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
        # 초기 짧은 응답 없이, 바로 백그라운드 편집 작업 시작
        job_id = _new_job(status="queued", message="대기열에 등록되었습니다.")
        asyncio.create_task(_run_background_job(job_id, state))

        return {
            **state,
            "result": {
                "success": True,
                "processing_type": "code_edit",
                "chat_message": "",  # 프론트에서 초기 메시지 표시 안 함
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

        project_root = str(settings.REACT_PROJECT_PATH)
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
        is_new_file = target_file and not resolve_src_path(target_file).exists()
        if is_new_file:
            # 확장자 기반으로 페이지/컴포넌트 추정 없이, 경로 규칙만 강제
            if target_file.startswith("client/pages/"):
                # 라우트 추가 보장 (App.tsx)
                try:
                    _ensure_route_in_app(target_file)
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
        applied = await file_mgr.apply_change(target_file, gen["updated_content"])
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
    ) -> Dict[str, Any]:
        initial: ChatState = {
            "messages": messages,
            "user_input": user_message,
            "chat_type": "",
            "selected_file": selected_file,
            "file_content": file_content,
            "model": model,
            "result": None,
        }
        final = await self.workflow.ainvoke(initial)
        return final.get("result", {})