import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from core.config import get_setting
from figma2code.convert_html.service.convert_html_service_abc import (
    ConvertHtmlServiceABC,
)
from figma2code.common.figma2html.figma_api_client import FigmaApiClient
from figma2code.common.figma2html.figma_url_parser import parse_figma_url
from figma2code.common.figma2html.html_generator import HtmlGenerator
from figma2code.common.figma2html.json_node_converter import (
    JsonNodeConverter,
)
from figma2code.common.figma2html.utils import (
    get_best_frame_from_page,
    inject_metadata,
    sanitize_filename,
)

settings = get_setting()


class ConvertHtmlService(ConvertHtmlServiceABC):
    def __init__(self):
        pass

    async def convert(
        self,
        figma_url: str,
        output_dir: str = "output",
        token: Optional[str] = None,
        embed_shapes: bool = True,
    ) -> Tuple[bool, str]:
        """
        Figma 디자인을 HTML/CSS로 변환하여 파일로 저장합니다.
        main.py를 import하지 않고 figma2html 하위 모듈을 직접 사용합니다.
        """
        try:
            file_key, node_id = parse_figma_url(figma_url)
            if not file_key:
                return (
                    False,
                    "잘못된 Figma URL입니다. 올바른 Figma 디자인 URL을 제공해주세요.",
                )

            # 클라이언트/컨버터/제너레이터 준비
            api_client = FigmaApiClient(token)
            json_converter = JsonNodeConverter()
            html_generator = HtmlGenerator(api_client=api_client)

            # 데이터 가져오기
            raw_nodes, node_name = await self._fetch_figma_data(
                api_client, html_generator, file_key, node_id, embed_shapes
            )
            if not raw_nodes:
                return False, "Figma 데이터를 가져오는데 실패했습니다"

            # 노드 변환
            conversion_settings = {
                "embedVectors": True,
                "useColorVariables": True,
                "htmlGenerationMode": "html",
            }
            processed_nodes, conversion_stats = json_converter.nodes_to_json(
                raw_nodes, conversion_settings
            )
            if not processed_nodes:
                return False, "처리된 노드가 없습니다"

            # HTML/CSS 생성
            html_settings = {
                "embedVectors": True,
                "embedImages": True,
                "embedShapes": embed_shapes,
                "htmlGenerationMode": "html",
            }
            html_generator.settings = html_settings
            result = html_generator.html_main(processed_nodes, is_preview=False)

            html_content = result.get("html", "")
            css_content = result.get("css", "")

            # 경고 표시 (로그)
            warnings = html_generator.get_warnings()
            if warnings:
                logging.warning(f"경고: {len(warnings)}개 문제 발견")
                for warning in warnings[:3]:
                    logging.warning(f" - {warning}")

            # 파일 저장
            return self._save_output_files(
                html_content, css_content, node_name, output_dir, conversion_stats
            )

        except ValueError as e:
            # FIGMA_API_TOKEN 누락 등 설정 오류
            logging.error(f"설정 오류: {e}")
            return False, f"설정 오류: {e}"
        except Exception as e:
            logging.error(f"변환 중 오류: {e}")
            return False, f"변환 중 오류 발생: {e}"

    async def _fetch_figma_data(
        self,
        api_client: FigmaApiClient,
        html_generator: HtmlGenerator,
        file_key: str,
        node_id: Optional[str],
        embed_shapes: bool,
    ) -> Tuple[Optional[List[Dict[str, Any]]], str]:
        """main.py의 _fetch_figma_data를 참고하여 데이터를 가져옵니다."""
        if node_id:
            rest_data = api_client.get_file_nodes_rest(file_key, [node_id])
            if (
                not rest_data
                or "nodes" not in rest_data
                or node_id not in rest_data["nodes"]
            ):
                return None, ""
            node_data = rest_data["nodes"][node_id]
            figma_node = node_data.get("document") if node_data else None
            if not figma_node:
                return None, ""
            node_name = figma_node.get("name", "figma_node")
            raw_nodes = [figma_node]
            for node in raw_nodes:
                inject_metadata(node, file_key, node_id)
        else:
            file_data = api_client.get_file(file_key)
            if not file_data:
                return None, ""
            document = file_data.get("document", {})
            children = document.get("children", [])
            if not children:
                return None, ""
            page = children[0]
            best_frame = get_best_frame_from_page(page)
            if best_frame:
                figma_node = best_frame
                node_name = figma_node.get("name", "figma_page")
            else:
                return None, ""
            raw_nodes = [figma_node]
            for node in raw_nodes:
                inject_metadata(node, file_key)

        # 원본 순서 정보 보존
        self._preserve_original_order(raw_nodes)

        # polygon/ellipse를 SVG로 처리
        if html_generator.svg_renderer and embed_shapes:
            try:
                raw_nodes = html_generator.svg_renderer.process_shapes_in_nodes(
                    raw_nodes, file_key
                )
            except Exception as e:
                logging.warning(f"SVG 처리 중 오류: {e}")

        return raw_nodes, node_name

    def _preserve_original_order(self, nodes: List[Dict[str, Any]]) -> None:
        """재귀적으로 원본 순서 정보를 보존"""

        def add_order_info(
            node_list: List[Dict[str, Any]], parent_name: str = "root"
        ) -> None:
            for i, node in enumerate(node_list):
                if node is not None:
                    node["_original_order"] = i
                    children = node.get("children", [])
                    if children:
                        add_order_info(children, node.get("name", "unknown"))

        add_order_info(nodes)

    def _save_output_files(
        self,
        html_content: str,
        css_content: str,
        node_name: str,
        output_dir: str,
        stats: Dict[str, Any],
    ) -> Tuple[bool, str]:
        try:
            frame_folder_name = sanitize_filename(node_name)
            output_path = os.path.join(output_dir, frame_folder_name)
            os.makedirs(output_path, exist_ok=True)
            complete_html = self._generate_complete_html(
                html_content, css_content, node_name
            )
            html_filename = f"{sanitize_filename(node_name)}.html"
            css_filename = f"{sanitize_filename(node_name)}.css"
            html_path = os.path.join(output_path, html_filename)
            css_path = os.path.join(output_path, css_filename)
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(complete_html)
            with open(css_path, "w", encoding="utf-8") as f:
                f.write(css_content)
            logging.info(f"HTML: {html_path}")
            logging.info(f"CSS: {css_path}")
            logging.info(
                f"성능: {stats.get('nodes_processed', 0)}개 노드 처리, {stats.get('groups_inlined', 0)}개 그룹 인라인"
            )
            return True, f"{output_path}에 성공적으로 저장되었습니다"
        except Exception as e:
            return False, f"파일 저장 중 오류: {e}"

    def _generate_complete_html(
        self, html_content: str, css_content: str, title: str
    ) -> str:
        css_filename = f"{sanitize_filename(title)}.css"
        return (
            "<!DOCTYPE html>\n"
            '<html lang="ko">\n'
            "<head>\n"
            '    <meta charset="UTF-8">\n'
            '    <meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
            f"    <title>{title}</title>\n"
            f'    <link rel="stylesheet" href="{css_filename}">\n'
            "</head>\n"
            "<body>\n"
            f"{html_content}\n"
            "</body>\n"
            "</html>"
        )


# FastAPI Depends 용 DI 팩토리
def get_convert_html_service() -> ConvertHtmlService:
    return ConvertHtmlService()
