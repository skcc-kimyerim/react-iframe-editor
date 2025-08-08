from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
import httpx
from ..core.config import settings

router = APIRouter(tags=["chat"])

OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/"


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str
    messages: list[ChatMessage]


class ChatResponse(BaseModel):
    content: str


@router.post("/chat", response_model=ChatResponse)
async def chat_proxy(req: ChatRequest):
    api_key = settings.OPENROUTER_API_KEY
    if not api_key:
        raise HTTPException(status_code=400, detail="OPENROUTER_API_KEY not configured on server")

    payload = {
        "model": req.model,
        "messages": [m.dict() for m in req.messages],
        "stream": False,
    }

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
        "HTTP-Referer": "http://localhost:3001",
        "X-Title": "React Iframe Editor",
    }

    try:
        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post(OPENROUTER_ENDPOINT, headers=headers, json=payload)
            if r.status_code != 200:
                raise HTTPException(status_code=r.status_code, detail=r.text)
            data = r.json()
            content = (
                data.get("choices", [{}])[0]
                .get("message", {})
                .get("content", "")
            )
            return ChatResponse(content=content or "")
    except httpx.RequestError as e:
        raise HTTPException(status_code=502, detail=f"Upstream error: {e}")

