from abc import ABC, abstractmethod
from typing import Optional, Tuple


class GeneratePageServiceABC(ABC):
    @abstractmethod
    def __init__(self):
        pass

    @abstractmethod
    async def generate(
        self,
        figma_url: str,
        output: str = "output",
        pages: Optional[str] = None,
        token: Optional[str] = None,
        components: Optional[str] = None,
        embed_shapes: bool = True,
    ) -> Tuple[bool, str]:
        """
        Figma 디자인 URL을 입력받아 페이지를 생성합니다.
        """
        pass
