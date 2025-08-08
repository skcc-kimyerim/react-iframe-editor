from pydantic import BaseModel
from typing import Dict, List

# Request 모델들
class ComponentUpdateRequest(BaseModel):
    content: str

class ProjectInitRequest(BaseModel):
    componentCode: str
    dependencies: Dict[str, str] = {}

class FileSaveRequest(BaseModel):
    relativePath: str
    content: str

class ChatRequest(BaseModel):
    messages: List[Dict[str, str]]
    model: str = "openai/gpt-4o-mini"

class ChatResponse(BaseModel):
    content: str
