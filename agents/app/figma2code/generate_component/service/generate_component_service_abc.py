from abc import ABC, abstractmethod
from typing import Optional, Tuple


class GenerateComponentServiceABC(ABC):
    @abstractmethod
    def __init__(self):
        pass

    @abstractmethod
    async def generate(
        self,
        figma_url: str,
        output: str = "output/frontend/components",
        token: Optional[str] = None,
        embed_shapes: bool = True,
    ) -> Tuple[bool, str]:
        """
        Figma 노드를 React TSX 컴포넌트로 변환하여 저장합니다.
        """
        pass
