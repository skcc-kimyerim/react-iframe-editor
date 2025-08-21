"""
Figma REST API Client
Figma API와 상호작용하는 클라이언트
"""

import logging
import os
from typing import Any, Dict, List, Optional

import aiohttp
import requests

from .utils import save_json_response

# 환경변수 로딩 시도
try:
    from dotenv import load_dotenv

    load_dotenv()
    load_dotenv(dotenv_path=".env")
    load_dotenv(dotenv_path="../.env")
    load_dotenv(dotenv_path="../../.env")
except ImportError:
    pass


class FigmaApiClient:
    """Figma REST API 클라이언트"""

    def __init__(self, api_token: Optional[str] = None):
        self.api_token = api_token or os.getenv("FIGMA_API_TOKEN")
        if not self.api_token:
            raise ValueError(
                "Figma API token is required. Set FIGMA_API_TOKEN environment variable or pass token directly."
            )
        self.base_url = "https://api.figma.com/v1"
        self.headers = {
            "X-Figma-Token": self.api_token,
            "Content-Type": "application/json",
        }
        # responses_dir 관련 부수효과 제거

    def clear_response_cache(self) -> None:
        """output/responses 디렉토리의 파일을 모두 삭제"""
        responses_dir = "output/responses"
        if os.path.exists(responses_dir):
            for filename in os.listdir(responses_dir):
                file_path = os.path.join(responses_dir, filename)
                if os.path.isfile(file_path):
                    os.remove(file_path)
        else:
            os.makedirs(responses_dir, exist_ok=True)

    def get_file(self, file_key: str) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/files/{file_key}"
        try:
            response = requests.get(url, headers=self.headers, verify=False)
            response.raise_for_status()
            data = response.json()
            save_json_response(data)
            return data
        except requests.RequestException as e:
            logging.error(f"파일 가져오기 실패: {e}")
            return None

    def get_file_nodes_rest(
        self, file_key: str, node_ids: List[str]
    ) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/files/{file_key}/nodes"
        params = {"ids": ",".join(node_ids)}
        try:
            response = requests.get(
                url, headers=self.headers, params=params, verify=False
            )
            response.raise_for_status()
            data = response.json()
            rest_nodes = {}
            if "nodes" in data:
                for node_id, node_data in data["nodes"].items():
                    if node_data and "document" in node_data:
                        document = node_data["document"]
                        self._enhance_node_for_rest(document)
                        rest_nodes[node_id] = {"document": document}
            result = {"nodes": rest_nodes}
            save_json_response(result)
            return result
        except requests.RequestException as e:
            logging.error(f"REST 형식 노드 가져오기 실패: {e}")
            return None

    def get_node(self, file_key: str, node_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/files/{file_key}/nodes"
        params = {"ids": node_id}
        try:
            response = requests.get(
                url, headers=self.headers, params=params, verify=False
            )
            response.raise_for_status()
            data = response.json()
            save_json_response(data)
            if "nodes" in data and node_id in data["nodes"]:
                return data["nodes"][node_id]
            return None
        except requests.RequestException as e:
            logging.error(f"노드 가져오기 실패: {e}")
            return None

    def get_images(
        self,
        file_key: str,
        node_ids: List[str],
        format: str = "png",
        scale: float = 1.0,
    ) -> Optional[Dict[str, str]]:
        url = f"{self.base_url}/images/{file_key}"
        params = {"ids": ",".join(node_ids), "format": format, "scale": scale}
        try:
            response = requests.get(
                url, headers=self.headers, params=params, verify=False
            )
            response.raise_for_status()
            data = response.json()
            save_json_response(data)
            return data.get("images")
        except requests.RequestException as e:
            logging.error(f"이미지 가져오기 실패: {e}")
            return None

    def get_svg_for_shapes(
        self,
        file_key: str,
        node_ids: List[str],
        scale: float = 1.0,
    ) -> Optional[Dict[str, str]]:
        """
        polygon과 ellipse 타입을 위한 SVG 렌더링

        Args:
            file_key: Figma 파일 키
            node_ids: 렌더링할 노드 ID 리스트
            scale: 이미지 스케일 (기본값: 1.0)

        Returns:
            노드 ID를 키로 하고 SVG URL을 값으로 하는 딕셔너리
        """
        url = f"{self.base_url}/images/{file_key}"
        params = {
            "ids": ",".join(node_ids),
            "format": "svg",
            "scale": scale,
            "use_absolute_bounds": "true",
        }

        logging.info(f"SVG 렌더링 요청: {url}")
        logging.info(f"파라미터: {params}")

        try:
            response = requests.get(
                url, headers=self.headers, params=params, verify=False
            )

            if response.status_code != 200:
                logging.error(f"SVG 렌더링 실패 - 상태 코드: {response.status_code}")
                logging.error(f"응답 내용: {response.text}")
                return None

            data = response.json()
            save_json_response(data)

            images = data.get("images", {})
            logging.info(f"렌더링 결과: {len(images)}개 노드")

            for node_id, image_url in images.items():
                if image_url:
                    logging.info(f"  ✅ {node_id}: 렌더링 성공")
                else:
                    logging.warning(f"  ❌ {node_id}: 렌더링 실패")

            return images

        except requests.RequestException as e:
            logging.error(f"SVG 렌더링 실패: {e}")
            return None

    def download_svg_content(self, svg_url: str) -> Optional[str]:
        """
        SVG URL에서 실제 SVG 콘텐츠를 다운로드

        Args:
            svg_url: SVG 이미지 URL

        Returns:
            SVG 콘텐츠 문자열 또는 None
        """
        try:
            response = requests.get(svg_url, verify=False)
            response.raise_for_status()
            return response.text
        except requests.RequestException as e:
            logging.error(f"SVG 다운로드 실패: {e}")
            return None

    def is_node_renderable(self, node_data: Dict[str, Any]) -> bool:
        """
        노드가 렌더링 가능한지 확인

        Args:
            node_data: 노드 데이터

        Returns:
            렌더링 가능 여부
        """
        # 노드가 보이지 않으면 렌더링 불가
        if not node_data.get("visible", True):
            return False

        # 투명도가 0이면 렌더링 불가
        if node_data.get("opacity", 1.0) == 0:
            return False

        # 크기가 0이면 렌더링 불가
        bbox = node_data.get("absoluteBoundingBox", {})
        if bbox.get("width", 0) <= 0 or bbox.get("height", 0) <= 0:
            return False

        # fills와 strokes가 모두 비어있어도 렌더링 가능 (투명한 도형도 렌더링 가능)
        # Figma API는 빈 도형도 SVG로 렌더링할 수 있음

        return True

    def get_shape_as_svg(
        self, file_key: str, node_id: str, node_data: Dict[str, Any]
    ) -> Optional[str]:
        """
        특정 도형 노드를 SVG로 렌더링하고 콘텐츠를 반환

        Args:
            file_key: Figma 파일 키
            node_id: 노드 ID
            node_data: 노드 데이터

        Returns:
            SVG 콘텐츠 문자열 또는 None
        """
        # polygon과 ellipse 타입만 처리
        node_type = node_data.get("type")
        if node_type not in ["ELLIPSE", "REGULAR_POLYGON"]:
            return None

        # 렌더링 가능한지 확인
        if not self.is_node_renderable(node_data):
            logging.warning(f"노드가 렌더링 불가능: {node_id} ({node_type})")
            return None

        try:
            # SVG 렌더링 요청
            images = self.get_svg_for_shapes(file_key, [node_id])
            if not images or node_id not in images or not images[node_id]:
                logging.warning(f"SVG 렌더링 실패: {node_id}")
                return None

            # SVG 콘텐츠 다운로드
            svg_url = images[node_id]
            svg_content = self.download_svg_content(svg_url)

            if svg_content:
                logging.info(f"SVG 렌더링 성공: {node_id} ({node_type})")
                return svg_content
            else:
                logging.warning(f"SVG 다운로드 실패: {node_id}")
                return None

        except Exception as e:
            logging.error(f"도형 SVG 처리 실패: {node_id}, {e}")
            return None

    async def get_file_nodes_async(
        self, file_key: str, node_ids: List[str]
    ) -> Optional[Dict[str, Any]]:
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/files/{file_key}/nodes"
            params = {"ids": ",".join(node_ids)}
            try:
                async with session.get(
                    url, headers=self.headers, params=params
                ) as response:
                    if response.status == 200:
                        return await response.json()
                    return None
            except Exception as e:
                logging.error(f"비동기 요청 실패: {e}")
                return None

    def _enhance_node_for_rest(self, node: Dict[str, Any]) -> None:
        if "visible" not in node:
            node["visible"] = True
        if "opacity" not in node:
            node["opacity"] = 1.0
        if "rotation" in node and node["rotation"] != 0:
            node["rotation"] = node["rotation"] * (3.14159 / 180)
        if "name" in node and "uniqueName" not in node:
            node["uniqueName"] = node["name"]
        node["canBeFlattened"] = node.get("type") in [
            "VECTOR",
            "STAR",
            "POLYGON",
            "BOOLEAN_OPERATION",
        ]
        node["isRelative"] = node.get("layoutMode") == "NONE"
        if "children" in node and isinstance(node["children"], list):
            for child in node["children"]:
                self._enhance_node_for_rest(child)


def create_figma_client(api_token: Optional[str] = None) -> FigmaApiClient:
    return FigmaApiClient(api_token)
