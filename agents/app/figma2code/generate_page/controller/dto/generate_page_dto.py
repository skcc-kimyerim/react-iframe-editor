from dataclasses import dataclass
from typing import Optional, Any


@dataclass(frozen=True)
class FigmaConvertResponseDTO:
    success: bool
    message: Any


@dataclass(frozen=True)
class FigmaCreatePageRequestDTO:
    figma_url: str
    output: str = "output"
    pages: Optional[str] = "output/frontend"
    token: Optional[str] = None
    components: Optional[str] = "output/frontend/components"
    embed_shapes: bool = True
