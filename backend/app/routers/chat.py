from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx
import json
import re
from ..core.config import settings
from ..services.chat_workflow import ChatWorkflow

router = APIRouter(tags=["chat"])

OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/"

# LangGraph 워크플로우 인스턴스 생성
chat_workflow = ChatWorkflow()


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str
    messages: list[ChatMessage]
    selectedFile: str | None = None  # 선택된 파일 경로
    fileContent: str | None = None   # 현재 파일 내용


class ChatResponse(BaseModel):
    content: str
    updatedFile: str | None = None      # 수정된 파일 경로 
    updatedContent: str | None = None   # 수정된 파일 내용


@router.post("/chat", response_model=ChatResponse)
async def chat_proxy(req: ChatRequest):
    # 1. 먼저 LangGraph 워크플로우로 처리 시도
    user_message = req.messages[-1].content if req.messages else ""
    print(user_message)
    
    try:
        # LangGraph 워크플로우 실행
        workflow_result = await chat_workflow.process_message(
            user_message=user_message,
            messages=[m.dict() for m in req.messages],
            selected_file=req.selectedFile,
            file_content=req.fileContent
        )
        
        # Figma 처리가 성공한 경우
        if workflow_result and workflow_result.get("success") and workflow_result.get("processing_type") in ["components", "page"]:
            chat_message = workflow_result.get("chat_message", "처리가 완료되었습니다.")
            
            # 에디터 업데이트 정보
            updated_file = None
            updated_content = None
            
            if workflow_result.get("editor_content"):
                updated_file = workflow_result.get("editor_filename", "src/components/figma_output.tsx")
                updated_content = workflow_result["editor_content"]
            
            print(chat_message)
            return ChatResponse(
                content=chat_message,
                updatedFile=updated_file,
                updatedContent=updated_content
            )
    
    except Exception as e:
        # LangGraph 처리 실패 시 로그만 남기고 기존 방식으로 fallback
        import logging
        logging.warning(f"LangGraph 워크플로우 처리 실패, fallback to OpenRouter: {e}")
    
    # 2. 기존 OpenRouter 방식으로 fallback
    api_key = settings.OPENROUTER_API_KEY
    if not api_key:
        raise HTTPException(status_code=400, detail="OPENROUTER_API_KEY not configured on server")

    # 메시지 목록 준비
    messages = [m.dict() for m in req.messages]
    
    # 파일이 선택된 경우, 시스템 메시지에 파일 정보 추가
    if req.selectedFile and req.fileContent is not None:
        system_message = {
            "role": "system", 
            "content": f"""당신은 React/TypeScript 코드 전문가입니다. 사용자가 선택한 파일에 대해 질문하거나 수정을 요청할 것입니다.

현재 선택된 파일: {req.selectedFile}
현재 파일 내용:
```
{req.fileContent}
```

사용자의 요청에 따라 코드를 수정해야 하는 경우, 다음 형식으로 응답해주세요:

1. 먼저 수정 내용에 대한 간단한 설명을 작성
2. 그 다음 수정된 전체 코드를 ```typescript 또는 ```javascript 블록 안에 작성

참고: 코드 블록은 자동으로 에디터에 반영되므로, 설명은 간단하고 명확하게 해주세요.
코드를 수정할 때는 기존 코드의 구조와 스타일을 유지하면서 요청된 기능만 추가/수정해주세요."""
        }
        messages.insert(0, system_message)

    payload = {
        "model": req.model,
        "messages": messages,
        "stream": False,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": f"http://localhost:{settings.PORT}",
        "X-Title": "React Iframe Editor",
    }

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(OPENROUTER_ENDPOINT + "chat/completions", headers=headers, json=payload)
            if r.status_code != 200:
                raise HTTPException(status_code=r.status_code, detail=f"API error: {r.text}")
            
            # 응답 텍스트가 비어있는지 확인
            if not r.text.strip():
                raise HTTPException(status_code=502, detail="Empty response from API")
            
            try:
                data = r.json()
            except json.JSONDecodeError as e:
                raise HTTPException(status_code=502, detail=f"Invalid JSON response: {r.text[:200]}...")
            
            # 응답 구조 검증
            if "choices" not in data or not data["choices"]:
                raise HTTPException(status_code=502, detail=f"Invalid response structure: {data}")
            
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            
            # 응답에서 코드 블록 추출
            updated_file = None
            updated_content = None
            display_content = content
            
            if req.selectedFile and content:
                # TypeScript/JavaScript 코드 블록 찾기
                code_blocks = re.findall(r'```(?:typescript|javascript|tsx|jsx)\n(.*?)\n```', content, re.DOTALL)
                if code_blocks:
                    updated_file = req.selectedFile
                    updated_content = code_blocks[0].strip()  # 첫 번째 코드 블록 사용
                    
                    # 채팅 표시용 응답에서는 코드 블록 제거하고 설명만 남김
                    display_content = re.sub(r'```(?:typescript|javascript|tsx|jsx)\n.*?\n```', '', content, flags=re.DOTALL)
                    display_content = display_content.strip()
                    
                    # 만약 설명이 거의 없다면 기본 메시지 추가
                    if len(display_content) < 10:
                        display_content = "코드가 수정되었습니다! 에디터에서 확인해보세요."
            
            print(display_content)
            return ChatResponse(
                content=display_content or "",
                updatedFile=updated_file,
                updatedContent=updated_content
            )
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Upstream error: {e}")
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=502, detail=f"JSON decode error: {e}")

