from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class ChatRequestDTO:
    chat_id: str
    message: str


@dataclass(frozen=True)
class ChatResponseDTO:
    id: str
    title: str


@dataclass(frozen=True)
class ChatMessageResponseDTO:
    id: str
    chat_id: str
    content: str


@dataclass(frozen=True)
class ChatMessageRequestDTO:
    chat_id: str
    user_id: str
    message: str


@dataclass(frozen=True)
class FigmaConvertRequestDTO:
    figma_url: str
    output_dir: str = "output"
    token: Optional[str] = None
    embed_shapes: bool = True


@dataclass(frozen=True)
class FigmaConvertResponseDTO:
    success: bool
    message: str


@dataclass(frozen=True)
class FigmaReactComponentRequestDTO:
    figma_url: str
    output: str = "output/frontend/components"
    token: Optional[str] = None
    embed_shapes: bool = True


@dataclass(frozen=True)
class FigmaCreatePageRequestDTO:
    figma_url: str
    output: str = "output"
    pages: Optional[str] = "output/frontend"
    token: Optional[str] = None
    components: Optional[str] = "output/frontend/components"
    embed_shapes: bool = True
