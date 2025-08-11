from langgraph.graph import StateGraph, END
from typing import TypedDict
import re
import httpx
import logging
from app.core.config import settings

class ChatState(TypedDict):
    messages: list[dict]
    user_input: str
    chat_type: str
    figma_url: str | None
    prefer_components: bool
    selected_file: str | None
    file_content: str | None
    result: dict | None

def classify_input_node(state: ChatState) -> ChatState:
    """사용자 입력을 분류하는 노드"""
    user_input = state["user_input"]
    
    # Figma URL 패턴 검사
    figma_pattern = r"figma\.com/design/([^/]+)/([^/]+)"
    
    chat_type = "general"
    figma_url = None
    prefer_components = False
    
    if re.search(figma_pattern, user_input):
        chat_type = "figma"
        figma_url = user_input
        
        # "컴포넌트" 키워드가 있으면 컴포넌트 추출 선호
        if "컴포넌트" in user_input or "component" in user_input.lower():
            prefer_components = True
    
    elif state.get("selected_file"):
        chat_type = "file_chat"
    
    return {
        **state,
        "chat_type": chat_type,
        "figma_url": figma_url,
        "prefer_components": prefer_components
    }

async def handle_figma_node(state: ChatState) -> ChatState:
    """Figma 처리 노드"""
    figma_url = state["figma_url"]
    prefer_components = state.get("prefer_components", False)
    
    try:
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
            f"http://localhost:{settings.PORT}/api/figma/process",
                json={
                    "figma_url": figma_url,
                    "prefer_components": prefer_components
                }
            )
            
            if response.status_code == 200:
                result = response.json()
                
                # 처리 결과에 따른 메시지 생성
                processing_type = result.get("processing_type", "unknown")
                
                if processing_type == "components":
                    success_count = result.get("success_count", 0)
                    total_count = result.get("total_count", 0)
                    message = f"🎨 Figma에서 {total_count}개의 컴포넌트 중 {success_count}개를 성공적으로 변환했습니다!"
                    
                    # 첫 번째 성공한 컴포넌트의 코드를 에디터에 표시
                    components = result.get("components", [])
                    for component in components:
                        if component.get("success") and component.get("code"):
                            result["editor_content"] = component["code"]
                            result["editor_filename"] = f"src/components/{component['component_name']}.tsx"
                            break
                
                elif processing_type == "page":
                    page_name = result.get("node_name", "페이지")        
            
                    message = f"📄 Figma 페이지 '{page_name}'를 React 페이지로 변환했습니다!"
                    result["editor_content"] = result["code"]
                    result["editor_filename"] = f"src/pages/{page_name}.tsx"                    
                
                else:
                    message = "✅ Figma 변환이 완료되었습니다!"
                
                result["chat_message"] = message
                
            else:
                result = {
                    "success": False,
                    "chat_message": f"❌ Figma 변환 실패: {response.text}",
                    "processing_type": "error"
                }
    
    except Exception as e:
        logging.error(f"Figma 처리 오류: {str(e)}")
        result = {
            "success": False,
            "chat_message": f"❌ 변환 중 오류가 발생했습니다: {str(e)}",
            "processing_type": "error"
        }
    
    return {**state, "result": result}

async def handle_file_chat_node(state: ChatState) -> ChatState:
    """파일 기반 채팅 처리 노드"""
    # 기존 파일 채팅 로직
    return {
        **state,
        "result": {
            "success": True,
            "chat_message": "파일 채팅 기능은 아직 구현 중입니다.",
            "processing_type": "file_chat"
        }
    }

async def handle_general_chat_node(state: ChatState) -> ChatState:
    """일반 채팅 처리 노드"""
    # 기존 일반 채팅 로직
    return {
        **state,
        "result": {
            "success": True,
            "chat_message": "일반 채팅 기능은 아직 구현 중입니다.",
            "processing_type": "general"
        }
    }

def should_continue(state: ChatState) -> str:
    """다음 노드 결정"""
    return state["chat_type"]

# LangGraph 워크플로우 구성
def create_chat_workflow():
    workflow = StateGraph(ChatState)
    
    # 노드 추가
    workflow.add_node("classify", classify_input_node)
    workflow.add_node("figma", handle_figma_node)
    workflow.add_node("file_chat", handle_file_chat_node)
    workflow.add_node("general", handle_general_chat_node)
    
    # 시작점 설정
    workflow.set_entry_point("classify")
    
    # 조건부 엣지 추가
    workflow.add_conditional_edges(
        "classify",
        should_continue,
        {
            "figma": "figma",
            "file_chat": "file_chat",
            "general": "general"
        }
    )
    
    # 종료 엣지 추가
    workflow.add_edge("figma", END)
    workflow.add_edge("file_chat", END)
    workflow.add_edge("general", END)
    
    return workflow.compile()

class ChatWorkflow:
    def __init__(self):
        self.workflow = create_chat_workflow()
    
    async def process_message(
        self, 
        user_message: str, 
        messages: list[dict],
        selected_file: str | None = None,
        file_content: str | None = None
    ) -> dict:
        """메시지 처리"""
        initial_state = {
            "messages": messages,
            "user_input": user_message,
            "chat_type": "",
            "figma_url": None,
            "prefer_components": False,
            "selected_file": selected_file,
            "file_content": file_content,
            "result": None
        }
        
        final_state = await self.workflow.ainvoke(initial_state)
        return final_state.get("result", {})