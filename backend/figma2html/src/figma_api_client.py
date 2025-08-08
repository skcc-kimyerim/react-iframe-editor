"""
Figma REST API Client
Figma API와 상호작용하는 클라이언트
"""

import os
import requests
import aiohttp
import logging
from typing import Optional, Dict, Any, List
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

    def clear_response_cache(self):
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
            response = requests.get(url, headers=self.headers)
            response.raise_for_status()
            data = response.json()
            save_json_response(data)
            return data
        except requests.RequestException as e:
            logging.error(f"파일 가져오기 실패: {e}")
            return None

    def get_file_nodes_rest(self, file_key: str, node_ids: List[str]) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/files/{file_key}/nodes"
        params = {"ids": ",".join(node_ids)}
        try:
            response = requests.get(url, headers=self.headers, params=params)
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
            response = requests.get(url, headers=self.headers, params=params)
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
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            data = response.json()
            save_json_response(data)
            return data.get("images")
        except requests.RequestException as e:
            logging.error(f"이미지 가져오기 실패: {e}")
            return None

    async def get_file_nodes_async(self, file_key: str, node_ids: List[str]) -> Optional[Dict[str, Any]]:
        async with aiohttp.ClientSession() as session:
            url = f"{self.base_url}/files/{file_key}/nodes"
            params = {"ids": ",".join(node_ids)}
            try:
                async with session.get(url, headers=self.headers, params=params) as response:
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
        node["canBeFlattened"] = node.get("type") in ["VECTOR", "STAR", "POLYGON", "BOOLEAN_OPERATION"]
        node["isRelative"] = node.get("layoutMode") == "NONE"
        if "children" in node and isinstance(node["children"], list):
            for child in node["children"]:
                self._enhance_node_for_rest(child)


def create_figma_client(api_token: Optional[str] = None) -> FigmaApiClient:
    return FigmaApiClient(api_token)
