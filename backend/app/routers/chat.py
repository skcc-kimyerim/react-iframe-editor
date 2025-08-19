from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import logging
from typing import Any, Dict, List, Optional
from ..services.chat_workflow import ChatWorkflow, get_job_status

router = APIRouter(tags=["chat"])

# 로거 설정
logger = logging.getLogger("app.chat")

# Orchestrator
chat_workflow = ChatWorkflow()


class ChatMessage(BaseModel):
    role: str
    content: str


class Attachment(BaseModel):
    url: str
    mime: Optional[str] = None
    name: Optional[str] = None
    size: Optional[int] = None


class ChatRequest(BaseModel):
    model: str
    messages: List[ChatMessage]
    selectedFile: Optional[str] = None   # 선택된 파일 경로
    fileContent: Optional[str] = None    # 현재 파일 내용
    attachments: Optional[List[Attachment]] = None  # 첨부 파일/이미지 목록
    projectName: str


class ChatResponse(BaseModel):
    content: str
    # 즉시 적용형 응답(하위호환)
    updatedFile: Optional[str] = None
    updatedContent: Optional[str] = None
    # 비동기 작업 추적용
    jobId: Optional[str] = None
    processingType: Optional[str] = None  # "general" | "code_analyze" | "code_edit"


@router.post("/chat", response_model=ChatResponse)
async def chat_proxy(req: ChatRequest):
    """
    - 동기: 즉시 채팅 응답 반환
    - 비동기: 코드 분석/생성/적용은 백그라운드 작업으로 진행 (jobId 발급)
    """
    try:
        user_message = req.messages[-1].content if req.messages else ""
        final_project_name = req.projectName or "default-project"
        
        result: Dict[str, Any] = await chat_workflow.process_message(
            user_message=user_message,
            messages=[m.dict() for m in req.messages],
            selected_file=req.selectedFile,
            file_content=req.fileContent,
            model=req.model,
            attachments=[a.dict() for a in (req.attachments or [])],
            project_name=final_project_name,
        )

        # 결과 구성
        content = result.get("chat_message", "") or ""
        processing_type = result.get("processing_type")
        job_id = result.get("job_id")

        # 하위호환: 동기 즉시 코드가 생성된 경우만 포함(일반적으로는 None)
        updated_file = result.get("editor_filename")
        updated_content = result.get("editor_content")

        return ChatResponse(
            content=content,
            updatedFile=updated_file,
            updatedContent=updated_content,
            jobId=job_id,
            processingType=processing_type,
        )
    except Exception as e:
        logger.exception("Chat processing failed")
        raise HTTPException(status_code=500, detail=str(e))


class JobStatusResponse(BaseModel):
    jobId: str
    status: str                  # "queued" | "running" | "done" | "error"
    message: Optional[str] = None
    # 사람이 읽을 수 있는 변경 설명(코드블록 제거본)
    display: Optional[str] = None
    updatedFile: Optional[str] = None
    updatedContent: Optional[str] = None
    error: Optional[str] = None


@router.get("/chat/jobs/{job_id}", response_model=JobStatusResponse)
async def chat_job_status(job_id: str):
    """
    백그라운드 코드 수정 작업 상태 조회.
    - done + updatedFile/updatedContent 가 있으면, 프론트는 저장/적용 로직에 재사용 가능
    """
    status = get_job_status(job_id)
    if not status:
        raise HTTPException(status_code=404, detail="Job not found")

    return JobStatusResponse(
        jobId=job_id,
        status=status.get("status", "unknown"),
        message=status.get("message"),
        display=status.get("display"),
        updatedFile=status.get("updatedFile"),
        updatedContent=status.get("updatedContent"),
        error=status.get("error"),
    )