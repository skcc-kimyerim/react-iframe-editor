from abc import ABC, abstractmethod
from typing import Optional, Tuple


class ConvertHtmlServiceABC(ABC):
    @abstractmethod
    def __init__(self):
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
