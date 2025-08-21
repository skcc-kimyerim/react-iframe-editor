"""
Batch Processor
API 호출과 다운로드를 병렬 처리하는 배치 프로세서
"""

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Set

import requests

from .figma_api_client import FigmaApiClient


@dataclass
class ApiRequest:
    """API 요청 정보"""

    file_key: str
    node_id: str
    format: str  # 'svg' 또는 'png'
    node: Dict[str, Any]
    request_type: str  # 'svg' 또는 'image'


@dataclass
class DownloadTask:
    """다운로드 작업 정보"""

    url: str
    node_id: str
    node: Dict[str, Any]
    format: str
    request_type: str


@dataclass
class ProcessedResult:
    """처리된 결과"""

    node_id: str
    node: Dict[str, Any]
    content: Optional[str]  # SVG 콘텐츠 또는 base64 이미지
    success: bool
    error: Optional[str] = None


class BatchProcessor:
    """Figma API 호출과 다운로드를 배치로 병렬 처리하는 클래스"""

    def __init__(self, api_client: FigmaApiClient):
        self.api_client = api_client
        self.worker_count = int(os.getenv("FIGMA_WORKER_COUNT", "4"))
        self.warnings: List[str] = []

    def process_nodes_batch(
        self, nodes: List[Dict[str, Any]], settings: Dict[str, Any]
    ) -> Dict[str, ProcessedResult]:
        """
        노드들을 배치로 처리

        Args:
            nodes: 처리할 노드 리스트
            settings: 처리 설정

        Returns:
            노드 ID를 키로 하는 처리 결과 딕셔너리
        """
        logging.info(f"배치 처리 시작: {len(nodes)}개 노드, {self.worker_count}개 워커")

        # 1. API 요청 수집
        api_requests = self._collect_api_requests(nodes, settings)
        logging.info(f"수집된 API 요청: {len(api_requests)}개")

        if not api_requests:
            return {}

        # 2. API 호출 배치 처리
        api_results = self._batch_api_calls(api_requests)
        logging.info(f"API 호출 완료: {len(api_results)}개 결과")

        # 3. 다운로드 작업 수집
        download_tasks = self._collect_download_tasks(api_results)
        logging.info(f"수집된 다운로드 작업: {len(download_tasks)}개")

        if not download_tasks:
            return {}

        # 4. 다운로드 배치 처리
        download_results = self._batch_downloads(download_tasks)
        logging.info(f"다운로드 완료: {len(download_results)}개 결과")

        # 5. 결과 처리
        processed_results = self._process_results(download_results, settings)
        logging.info(f"배치 처리 완료: {len(processed_results)}개 결과")

        return processed_results

    def _collect_api_requests(
        self, nodes: List[Dict[str, Any]], settings: Dict[str, Any]
    ) -> List[ApiRequest]:
        """API 요청들을 수집 - 원본 순서 유지"""
        requests = []
        processed_node_ids: Set[str] = set()

        # 원본 순서 정보가 있으면 정렬
        has_original_order = any(
            node.get("_original_order") is not None for node in nodes
        )
        if has_original_order:
            nodes = sorted(
                nodes, key=lambda node: node.get("_original_order", float("inf"))
            )
            logging.debug(
                "[BATCH ORDER] Sorted nodes by original order for batch processing"
            )

        for node in nodes:
            node_requests = self._collect_node_api_requests(
                node, settings, processed_node_ids
            )
            requests.extend(node_requests)

        return requests

    def _collect_node_api_requests(
        self,
        node: Dict[str, Any],
        settings: Dict[str, Any],
        processed_node_ids: Set[str],
    ) -> List[ApiRequest]:
        """단일 노드에서 API 요청 수집"""
        requests = []

        file_key = node.get("file_key")
        node_id = node.get("node_id")

        if not file_key or not node_id or node_id in processed_node_ids:
            return requests

        processed_node_ids.add(node_id)

        # SVG 요청 수집
        if (
            settings.get("embedVectors")
            and node.get("canBeFlattened")
            and not node.get("svg")
        ):
            requests.append(
                ApiRequest(
                    file_key=file_key,
                    node_id=node_id,
                    format="svg",
                    node=node,
                    request_type="svg",
                )
            )

        # 이미지 요청 수집
        if (
            settings.get("embedImages")
            and self._node_has_image_fill(node)
            and not node.get("base64")
        ):
            requests.append(
                ApiRequest(
                    file_key=file_key,
                    node_id=node_id,
                    format="png",
                    node=node,
                    request_type="image",
                )
            )

        # 자식 노드 처리
        children = node.get("children", [])
        for child in children:
            child_requests = self._collect_node_api_requests(
                child, settings, processed_node_ids
            )
            requests.extend(child_requests)

        return requests

    def _batch_api_calls(
        self, api_requests: List[ApiRequest]
    ) -> Dict[str, Dict[str, Any]]:
        """API 호출들을 배치로 처리"""
        if not api_requests:
            return {}

        # 파일키별로 요청 그룹화
        file_groups = {}
        for req in api_requests:
            if req.file_key not in file_groups:
                file_groups[req.file_key] = {"svg": [], "png": []}
            file_groups[req.file_key][req.format].append(req)

        results = {}

        # ThreadPoolExecutor로 병렬 처리
        with ThreadPoolExecutor(max_workers=self.worker_count) as executor:
            future_to_req = {}

            # 각 파일키별로 API 호출 제출
            for file_key, groups in file_groups.items():
                for format_type, reqs in groups.items():
                    if reqs:
                        node_ids = [req.node_id for req in reqs]
                        future = executor.submit(
                            self._call_figma_api, file_key, node_ids, format_type
                        )
                        future_to_req[future] = (file_key, format_type, reqs)

            # 결과 수집
            for future in as_completed(future_to_req):
                file_key, format_type, reqs = future_to_req[future]
                try:
                    api_result = future.result()
                    if api_result:
                        for req in reqs:
                            if req.node_id in api_result:
                                results[req.node_id] = {
                                    "url": api_result[req.node_id],
                                    "request": req,
                                }
                except Exception as e:
                    logging.error(
                        f"API 호출 실패 - 파일: {file_key}, 형식: {format_type}, 오류: {str(e)}"
                    )
                    self._add_warning(f"API 호출 실패: {file_key}")

        return results

    def _call_figma_api(
        self, file_key: str, node_ids: List[str], format_type: str
    ) -> Optional[Dict[str, str]]:
        """Figma API 호출"""
        try:
            return self.api_client.get_images(file_key, node_ids, format=format_type)
        except Exception as e:
            logging.error(f"Figma API 호출 오류: {str(e)}")
            return None

    def _collect_download_tasks(
        self, api_results: Dict[str, Dict[str, Any]]
    ) -> List[DownloadTask]:
        """다운로드 작업들을 수집"""
        tasks = []

        for node_id, result in api_results.items():
            url = result.get("url")
            request = result.get("request")

            if url and request:
                tasks.append(
                    DownloadTask(
                        url=url,
                        node_id=node_id,
                        node=request.node,
                        format=request.format,
                        request_type=request.request_type,
                    )
                )

        return tasks

    def _batch_downloads(
        self, download_tasks: List[DownloadTask]
    ) -> Dict[str, Dict[str, Any]]:
        """다운로드들을 배치로 처리"""
        if not download_tasks:
            return {}

        results = {}

        # ThreadPoolExecutor로 병렬 다운로드
        with ThreadPoolExecutor(max_workers=self.worker_count) as executor:
            future_to_task = {}

            # 다운로드 작업 제출
            for task in download_tasks:
                future = executor.submit(self._download_content, task.url)
                future_to_task[future] = task

            # 결과 수집
            for future in as_completed(future_to_task):
                task = future_to_task[future]
                try:
                    content = future.result()
                    results[task.node_id] = {
                        "content": content,
                        "task": task,
                        "success": content is not None,
                    }
                except Exception as e:
                    logging.error(f"다운로드 실패 - URL: {task.url}, 오류: {str(e)}")
                    results[task.node_id] = {
                        "content": None,
                        "task": task,
                        "success": False,
                        "error": str(e),
                    }
                    self._add_warning(f"다운로드 실패: {task.node_id}")

        return results

    def _download_content(self, url: str) -> Optional[bytes]:
        """콘텐츠 다운로드 - 모든 콘텐츠를 바이너리로 처리"""
        try:
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                return response.content
            else:
                logging.error(
                    f"다운로드 실패 - 상태코드: {response.status_code}, URL: {url}"
                )
                return None
        except Exception as e:
            logging.error(f"다운로드 오류: {str(e)}")
            return None

    def _process_results(
        self, download_results: Dict[str, Dict[str, Any]], settings: Dict[str, Any]
    ) -> Dict[str, ProcessedResult]:
        """다운로드 결과를 처리"""
        processed = {}

        for node_id, result in download_results.items():
            task = result["task"]
            content = result["content"]
            success = result["success"]

            if success and content:
                if task.request_type == "svg":
                    # SVG를 텍스트로 디코딩 후 처리
                    try:
                        svg_text = content.decode("utf-8")
                        processed_content = self._process_svg_content(
                            svg_text, task.node
                        )
                        processed[node_id] = ProcessedResult(
                            node_id=node_id,
                            node=task.node,
                            content=processed_content,
                            success=True,
                        )
                    except UnicodeDecodeError:
                        # 바이너리 SVG를 base64로 변환
                        import base64

                        b64_content = base64.b64encode(content).decode("utf-8")
                        data_uri = f"data:image/svg+xml;base64,{b64_content}"
                        processed[node_id] = ProcessedResult(
                            node_id=node_id,
                            node=task.node,
                            content=data_uri,
                            success=True,
                        )
                elif task.request_type == "image":
                    # 이미지를 base64로 변환
                    import base64

                    b64_content = base64.b64encode(content).decode("utf-8")
                    data_uri = f"data:image/png;base64,{b64_content}"
                    processed[node_id] = ProcessedResult(
                        node_id=node_id, node=task.node, content=data_uri, success=True
                    )
            else:
                # 실패한 경우 플레이스홀더 생성
                placeholder_content = self._create_placeholder_content(task)
                processed[node_id] = ProcessedResult(
                    node_id=node_id,
                    node=task.node,
                    content=placeholder_content,
                    success=False,
                    error=result.get("error"),
                )

        return processed

    def _process_svg_content(self, svg_content: str, node: Dict[str, Any]) -> str:
        """SVG 콘텐츠 처리 (색상 변수 대체 등)"""
        # 기존 SVGRenderer의 _process_svg_colors 로직 적용
        color_mappings = node.get("colorVariableMappings", {})
        if not color_mappings:
            return svg_content

        import re

        processed_svg = svg_content

        # fill="COLOR" 또는 stroke="COLOR" 패턴 대체
        color_attribute_regex = r'(fill|stroke)="([^"]*)"'

        def replace_color_attribute(match: Any) -> str:
            attribute = match.group(1)
            color_value = match.group(2)
            normalized_color = color_value.lower().strip()

            mapping = color_mappings.get(normalized_color)
            if mapping:
                variable_name = mapping.get("variableName")
                if variable_name:
                    return f'{attribute}="var(--{variable_name}, {color_value})"'
            return match.group(0)

        processed_svg = re.sub(
            color_attribute_regex, replace_color_attribute, processed_svg
        )

        # SVG 최적화: 불필요한 공백 제거
        processed_svg = re.sub(r"\s+", " ", processed_svg).strip()

        return processed_svg

    def _create_placeholder_content(self, task: DownloadTask) -> str:
        """플레이스홀더 콘텐츠 생성"""
        width = task.node.get("width", 24)
        height = task.node.get("height", 24)

        if task.request_type == "svg":
            # 최적화된 SVG 플레이스홀더
            placeholder_svg = f'<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg"><rect width="{width}" height="{height}" fill="#F3F4F6"/><path d="M8 8L16 16M16 8L8 16" stroke="#9CA3AF" stroke-width="2" stroke-linecap="round"/></svg>'
            return placeholder_svg
        else:
            # 투명 PNG base64
            transparent_png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
            return f"data:image/png;base64,{transparent_png_b64}"

    def _node_has_image_fill(self, node: Dict[str, Any]) -> bool:
        """노드가 이미지 fill을 가지고 있는지 확인"""
        fills = node.get("fills", [])
        if not isinstance(fills, list):
            return False
        return any(fill.get("type") == "IMAGE" for fill in fills)

    def _add_warning(self, message: str) -> None:
        """경고 메시지 추가"""
        if message not in self.warnings:
            self.warnings.append(message)

    def get_warnings(self) -> List[str]:
        """모든 경고 가져오기"""
        return self.warnings.copy()

    def clear_warnings(self) -> None:
        """경고 초기화"""
        self.warnings.clear()


def create_batch_processor(api_client: FigmaApiClient) -> BatchProcessor:
    """배치 프로세서 팩토리 함수"""
    return BatchProcessor(api_client)
