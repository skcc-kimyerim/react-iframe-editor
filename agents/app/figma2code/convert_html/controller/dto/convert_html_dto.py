from dataclasses import dataclass
from typing import Optional, Any


@dataclass(frozen=True)
class FigmaConvertRequestDTO:
    figma_url: str
    output_dir: str = "output"
    token: Optional[str] = None
    embed_shapes: bool = True


@dataclass(frozen=True)
class FigmaConvertResponseDTO:
    success: bool
    message: Any
