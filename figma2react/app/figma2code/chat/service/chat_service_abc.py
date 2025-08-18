from abc import ABC, abstractmethod
from typing import Optional, Tuple

from figma2code.chat.controller.dto.chat_dto import (
    ChatMessageRequestDTO,
    ChatMessageResponseDTO,
)


class ChatServiceABC(ABC):
    @abstractmethod
    def __init__(self):
        pass

    @abstractmethod
    async def process_chat_message(
        self,
        command: ChatMessageRequestDTO,
    ) -> ChatMessageResponseDTO:
        pass

    @abstractmethod
    async def convert(
        self,
        figma_url: str,
        output_dir: str = "output",
        token: Optional[str] = None,
        embed_shapes: bool = True,
    ) -> Tuple[bool, str]:
        """
        Figma 디자인 URL을 입력받아 HTML/CSS로 변환하고 파일로 저장합니다.

        Args:
            figma_url: Figma 디자인 URL
            output_dir: 출력 루트 디렉토리 (기본값: "output")
            token: Figma API 토큰 (미지정 시 환경변수 사용)
            embed_shapes: polygon/ellipse를 SVG로 처리 여부

        Returns:
            (성공 여부, 메시지 또는 출력 경로)
        """
        pass

    @abstractmethod
    async def convert_react_component(
        self,
        figma_url: str,
        output: str = "output/frontend/components",
        token: Optional[str] = None,
        embed_shapes: bool = True,
    ) -> Tuple[bool, str]:
        """
        Figma 노드 1개를 React TSX 컴포넌트로 변환하여 저장합니다.
        """
        pass

    @abstractmethod
    async def create_page(
        self,
        figma_url: str,
        output: str = "output",
        pages: Optional[str] = None,
        token: Optional[str] = None,
        components: Optional[str] = None,
        embed_shapes: bool = True,
    ) -> Tuple[bool, str]:
        """
        HTML/CSS 생성 후 LLM으로 TSX 페이지를 생성하여 저장합니다.
        """
        pass
