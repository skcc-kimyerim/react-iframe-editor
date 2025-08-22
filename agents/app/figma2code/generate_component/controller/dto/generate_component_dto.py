from dataclasses import dataclass
from typing import Optional, Any


@dataclass(frozen=True)
class FigmaConvertResponseDTO:
    success: bool
    message: Any


@dataclass(frozen=True)
class FigmaReactComponentRequestDTO:
    figma_url: str
    output: str = "output/frontend/components"
    token: Optional[str] = None
    embed_shapes: bool = True


@dataclass(frozen=True)
class FigmaComponentSimilarityRequestDTO:
    figma_url: str
    token: Optional[str] = None
    embed_shapes: bool = True
    guide_md_path: Optional[str] = "./output/frontend/COMPONENTS_GUIDE.md"
