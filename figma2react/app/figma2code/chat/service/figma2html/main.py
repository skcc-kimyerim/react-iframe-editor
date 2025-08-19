"""
Figma to Code - Python Implementation
Figma 디자인을 HTML/CSS로 변환하는 메인 CLI 인터페이스
"""

import os
import sys
import time
import traceback
from typing import Any, Dict, List, Optional, Tuple

import click
from colorama import Fore, Style, init

# 부모 디렉토리를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import logging

from .figma_api_client import FigmaApiClient
from .figma_url_parser import parse_figma_url
from .html_generator import HtmlGenerator
from .json_node_converter import JsonNodeConverter
from .utils import get_best_frame_from_page, inject_metadata, sanitize_filename

log_level = os.getenv("LOG_LEVEL", "INFO").upper()
logging.basicConfig(level=getattr(logging, log_level, logging.INFO))

# 컬러 출력 초기화
init()


class FigmaToCode:
    """Figma를 HTML/CSS로 변환하는 메인 클래스"""

    def __init__(self, api_token: Optional[str] = None):
        self.api_client = FigmaApiClient(api_token)
        self.json_converter = JsonNodeConverter()
        self.html_generator = HtmlGenerator(api_client=self.api_client)

    def convert_from_url(
        self, figma_url: str, output_dir: str = "output", embed_shapes: bool = True
    ) -> Tuple[bool, str]:
        try:
            logging.info(
                f"{Fore.BLUE}🔄 Figma URL 파싱 중: {figma_url}{Style.RESET_ALL}"
            )
            file_key, node_id = parse_figma_url(figma_url)

            if not file_key:
                return (
                    False,
                    "잘못된 Figma URL입니다. 올바른 Figma 디자인 URL을 제공해주세요.",
                )

            logging.debug(f"{Fore.BLUE}📂 파일 키: {file_key}{Style.RESET_ALL}")
            if node_id:
                logging.debug(f"{Fore.BLUE}🎯 노드 ID: {node_id}{Style.RESET_ALL}")

            # 데이터 가져오기
            raw_nodes, node_name = self._fetch_figma_data(file_key, node_id)
            if not raw_nodes:
                return False, "Figma 데이터를 가져오는데 실패했습니다"

            logging.info(f"{Fore.GREEN}✅ Figma 데이터 가져오기 성공{Style.RESET_ALL}")

            # 노드 처리
            logging.info(
                f"{Fore.YELLOW}🔄 고급 컨버터로 노드 처리 중...{Style.RESET_ALL}"
            )

            # 디버깅: raw_nodes 확인
            logging.debug(f"{Fore.CYAN}🔍 raw_nodes 타입: {type(raw_nodes)}")
            logging.debug(
                f"{Fore.CYAN}🔍 raw_nodes 길이: {len(raw_nodes) if raw_nodes else 0}"
            )
            if raw_nodes:
                logging.debug(
                    f"{Fore.CYAN}🔍 첫 번째 raw_node: {raw_nodes[0].get('type', 'unknown') if raw_nodes[0] else 'None'}"
                )

            conversion_settings = {
                "embedVectors": True,
                "useColorVariables": True,
                "htmlGenerationMode": "html",
            }

            try:
                processed_nodes, conversion_stats = self.json_converter.nodes_to_json(
                    raw_nodes, conversion_settings
                )
            except Exception as e:
                logging.error(
                    f"{Fore.RED}❌ json_converter.nodes_to_json 오류: {str(e)}"
                )

                logging.error(traceback.format_exc())
                return False, f"노드 변환 중 오류: {str(e)}"

            logging.debug(
                f"{Fore.CYAN}📊 변환 통계: {conversion_stats}{Style.RESET_ALL}"
            )

            if not processed_nodes:
                return False, "처리된 노드가 없습니다"

            # HTML/CSS 생성
            logging.info(f"{Fore.YELLOW}🔄 HTML/CSS 생성 중...{Style.RESET_ALL}")

            # 디버깅: processed_nodes 확인
            logging.debug(
                f"{Fore.CYAN}🔍 processed_nodes 타입: {type(processed_nodes)}"
            )
            logging.debug(
                f"{Fore.CYAN}🔍 processed_nodes 길이: {len(processed_nodes) if processed_nodes else 0}"
            )
            if processed_nodes:
                logging.debug(
                    f"{Fore.CYAN}🔍 첫 번째 노드: {processed_nodes[0].get('type', 'unknown') if processed_nodes[0] else 'None'}"
                )

            html_settings = {
                "embedVectors": True,
                "embedImages": True,
                "embedShapes": embed_shapes,  # CLI 옵션에서 받은 값 사용
                "htmlGenerationMode": "html",
            }

            self.html_generator.settings = html_settings
            result = self.html_generator.html_main(processed_nodes, is_preview=False)

            html_content = result["html"]
            css_content = result["css"]

            # 경고 표시
            warnings = self.html_generator.get_warnings()
            if warnings:
                logging.warning(
                    f"{Fore.YELLOW}⚠️  경고: {len(warnings)}개 문제 발견{Style.RESET_ALL}"
                )
                for warning in warnings[:3]:
                    logging.warning(f"   • {warning}")
                if len(warnings) > 3:
                    logging.warning(f"   • ... 그리고 {len(warnings) - 3}개 더")

            # 파일 저장
            return self._save_output_files(
                html_content, css_content, node_name, output_dir, conversion_stats
            )

        except Exception as e:
            return False, f"변환 중 오류 발생: {str(e)}"

    def _fetch_figma_data(
        self, file_key: str, node_id: Optional[str]
    ) -> Tuple[Optional[list], str]:
        if node_id:
            logging.info(
                f"{Fore.YELLOW}🔄 REST 형식으로 특정 노드 가져오는 중...{Style.RESET_ALL}"
            )
            rest_data = self.api_client.get_file_nodes_rest(file_key, [node_id])
            if (
                not rest_data
                or "nodes" not in rest_data
                or node_id not in rest_data["nodes"]
            ):
                return None, ""
            node_data = rest_data["nodes"][node_id]
            logging.debug(
                f"{Fore.CYAN}🔍 노드 데이터 키: {list(node_data.keys()) if node_data else 'None'}{Style.RESET_ALL}"
            )
            figma_node = node_data.get("document")
            if not figma_node:
                logging.error(
                    f"{Fore.RED}❌ 노드 데이터에서 document를 찾을 수 없습니다{Style.RESET_ALL}"
                )
                logging.warning(
                    f"{Fore.YELLOW}📋 node_data 내용: {node_data}{Style.RESET_ALL}"
                )
                return None, ""
            node_name = figma_node.get("name", "figma_node")
            raw_nodes = [figma_node]
            logging.debug(
                f"{Fore.CYAN}📝 선택된 노드 ID: '{node_id}', 이름: '{node_name}'{Style.RESET_ALL}"
            )
            for node in raw_nodes:
                inject_metadata(node, file_key, node_id)
        else:
            logging.info(f"{Fore.YELLOW}🔄 전체 파일 가져오는 중...{Style.RESET_ALL}")
            file_data = self.api_client.get_file(file_key)
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
                logging.debug(
                    f"{Fore.CYAN}📝 선택된 프레임: '{node_name}'{Style.RESET_ALL}"
                )
            else:
                return None, ""
            raw_nodes = [figma_node]
            for node in raw_nodes:
                inject_metadata(node, file_key)

        # 원본 순서 정보 보존
        self._preserve_original_order(raw_nodes)

        # polygon과 ellipse 타입을 SVG로 처리
        if self.html_generator.svg_renderer:
            logging.info(
                f"{Fore.YELLOW}🔄 polygon과 ellipse 타입을 SVG로 처리 중...{Style.RESET_ALL}"
            )
            try:
                raw_nodes = self.html_generator.svg_renderer.process_shapes_in_nodes(
                    raw_nodes, file_key
                )
                logging.info(f"{Fore.GREEN}✅ SVG 처리 완료{Style.RESET_ALL}")
            except Exception as e:
                logging.warning(
                    f"{Fore.YELLOW}⚠️ SVG 처리 중 오류: {str(e)}{Style.RESET_ALL}"
                )

        return raw_nodes, node_name

    def _preserve_original_order(self, nodes: List[Dict[str, Any]]) -> None:
        """재귀적으로 원본 순서 정보를 보존"""

        def add_order_info(
            node_list: List[Dict[str, Any]], parent_name: str = "root"
        ) -> None:
            for i, node in enumerate(node_list):
                if node:
                    node["_original_order"] = i
                    logging.debug(
                        f"[ORDER PRESERVE] '{node.get('name', 'unknown')}' in '{parent_name}' with order {i}"
                    )

                    # 자식 노드들도 재귀적으로 처리
                    children = node.get("children", [])
                    if children:
                        add_order_info(children, node.get("name", "unknown"))

        add_order_info(nodes)
        logging.info(f"{Fore.CYAN}📋 원본 순서 정보 보존 완료{Style.RESET_ALL}")

    def _save_output_files(
        self,
        html_content: str,
        css_content: str,
        node_name: str,
        output_dir: str,
        stats: dict,
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
            logging.info(
                f"{Fore.GREEN}✅ 변환이 성공적으로 완료되었습니다!{Style.RESET_ALL}"
            )
            logging.info(f"{Fore.CYAN}📄 HTML: {html_path}{Style.RESET_ALL}")
            logging.info(f"{Fore.CYAN}🎨 CSS: {css_path}{Style.RESET_ALL}")
            logging.info(
                f"{Fore.BLUE}📊 성능: {stats['nodes_processed']}개 노드 처리, "
                f"{stats['groups_inlined']}개 그룹 인라인{Style.RESET_ALL}"
            )
            return True, f"{output_path}에 성공적으로 저장되었습니다"
        except Exception as e:
            return False, f"파일 저장 중 오류: {str(e)}"

    def _generate_complete_html(
        self, html_content: str, css_content: str, title: str
    ) -> str:
        css_filename = f"{sanitize_filename(title)}.css"
        return f"""<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <link rel="stylesheet" href="{css_filename}">
</head>
<body>
{html_content}
</body>
</html>"""


@click.command()
@click.argument("figma_url", required=False)
@click.option("--output", "-o", default="output", help="생성된 파일의 출력 디렉토리")
@click.option(
    "--token", "-t", help="Figma API 토큰 (또는 FIGMA_API_TOKEN 환경변수 설정)"
)
@click.option(
    "--embed-shapes",
    is_flag=True,
    default=True,
    help="polygon과 ellipse를 SVG로 처리 (기본값: True)",
)
def convert(
    figma_url: Optional[str], output: str, token: Optional[str], embed_shapes: bool
) -> None:
    """
    Figma 디자인을 HTML/CSS로 변환

    FIGMA_URL: Figma 디자인 URL (예: https://www.figma.com/design/...)
    """
    try:
        # URL이 없으면 입력 받기
        if not figma_url:
            figma_url = click.prompt(
                "Figma 디자인 URL을 입력하세요",
                type=str,
            )

        converter = FigmaToCode(token)
        # response 캐시 삭제
        converter.api_client.clear_response_cache()

        # embed_shapes 설정을 HTML 생성기에 전달
        converter.html_generator.settings["embedShapes"] = embed_shapes

        success, message = converter.convert_from_url(figma_url, output, embed_shapes)
        if success:
            logging.info(f"{Fore.GREEN}🎉 {message}{Style.RESET_ALL}")
        else:
            logging.error(f"{Fore.RED}❌ {message}{Style.RESET_ALL}")
            sys.exit(1)
    except ValueError as e:
        logging.error(f"{Fore.RED}❌ 설정 오류: {e}{Style.RESET_ALL}")
        logging.warning(
            f"{Fore.YELLOW}💡 FIGMA_API_TOKEN 환경변수를 설정하거나 --token 옵션을 사용하세요{Style.RESET_ALL}"
        )
        logging.warning(
            f"{Fore.YELLOW}   토큰 발급: https://www.figma.com/developers/api#access-tokens{Style.RESET_ALL}"
        )
        sys.exit(1)
    except Exception as e:
        logging.error(f"{Fore.RED}❌ 예상치 못한 오류: {e}{Style.RESET_ALL}")
        sys.exit(1)


@click.group()
def cli() -> None:
    """Figma to Code - 고급 처리로 Figma 디자인을 HTML/CSS로 변환"""
    pass


@cli.command()
@click.argument("figma_url", required=False)
def info(figma_url: Optional[str]) -> None:
    """Figma 디자인 URL 정보 확인"""
    # URL이 없으면 입력 받기
    if not figma_url:
        figma_url = click.prompt(
            "Figma 디자인 URL을 입력하세요",
            type=str,
        )

    file_key, node_id = parse_figma_url(figma_url)
    if file_key:
        logging.info(f"{Fore.GREEN}✅ 유효한 Figma URL{Style.RESET_ALL}")
        logging.info(f"{Fore.CYAN}📂 파일 키: {file_key}{Style.RESET_ALL}")
        if node_id:
            logging.info(f"{Fore.CYAN}🎯 노드 ID: {node_id}{Style.RESET_ALL}")
        else:
            logging.warning(
                f"{Fore.YELLOW}ℹ️  특정 노드가 선택되지 않음 (전체 파일 변환){Style.RESET_ALL}"
            )
    else:
        logging.error(f"{Fore.RED}❌ 잘못된 Figma URL{Style.RESET_ALL}")
        logging.warning(
            f"{Fore.YELLOW}💡 예상 형식: https://www.figma.com/design/[file-key]/[name]?node-id=[node-id]{Style.RESET_ALL}"
        )


@cli.command()
def setup() -> None:
    """Figma API 토큰 설정 안내"""
    logging.info(f"{Fore.BLUE}🔧 Figma to Code 설정{Style.RESET_ALL}")
    logging.info("이 도구를 사용하려면 Figma API 토큰이 필요합니다:")
    logging.info(
        f"{Fore.YELLOW}1. 다음 링크로 이동: https://www.figma.com/developers/api#access-tokens{Style.RESET_ALL}"
    )
    logging.info(
        f"{Fore.YELLOW}2. 'Create a new personal access token' 클릭{Style.RESET_ALL}"
    )
    logging.info(f"{Fore.YELLOW}3. 이름을 지정하고 토큰 복사{Style.RESET_ALL}")
    logging.info(f"{Fore.YELLOW}4. 환경변수로 설정:{Style.RESET_ALL}")
    logging.info()
    logging.info(
        f"{Fore.GREEN}   export FIGMA_API_TOKEN=your_token_here{Style.RESET_ALL}"
    )
    logging.info()
    logging.info("또는 프로젝트 디렉토리에 .env 파일 생성:")
    logging.info()
    logging.info(f"{Fore.GREEN}   FIGMA_API_TOKEN=your_token_here{Style.RESET_ALL}")
    logging.info()
    logging.info(
        f"{Fore.CYAN}💡 convert 명령에서 --token 옵션도 사용할 수 있습니다{Style.RESET_ALL}"
    )


@cli.command()
@click.argument("figma_url", required=False)
@click.option("--token", "-t", help="Figma API 토큰")
def benchmark(figma_url: Optional[str], token: Optional[str]) -> None:
    """변환 성능 벤치마크"""
    # URL이 없으면 입력 받기
    if not figma_url:
        figma_url = click.prompt(
            "Figma 디자인 URL을 입력하세요",
            type=str,
        )

    logging.info(f"{Fore.BLUE}🏃 성능 벤치마크 실행 중...{Style.RESET_ALL}")
    try:
        converter = FigmaToCode(token)
        file_key, node_id = parse_figma_url(figma_url)
        if not file_key:
            logging.error(f"{Fore.RED}❌ 잘못된 URL{Style.RESET_ALL}")
            return
        start_time = time.time()
        raw_nodes, node_name = converter._fetch_figma_data(file_key, node_id)
        api_time = time.time() - start_time
        if not raw_nodes:
            logging.error(f"{Fore.RED}❌ 데이터 가져오기 실패{Style.RESET_ALL}")
            return
        start_time = time.time()
        processed_nodes, stats = converter.json_converter.nodes_to_json(raw_nodes)
        conversion_time = time.time() - start_time
        start_time = time.time()
        result = converter.html_generator.html_main(processed_nodes)
        generation_time = time.time() - start_time
        logging.info(f"{Fore.GREEN}📊 성능 결과:{Style.RESET_ALL}")
        logging.info(f"   API 가져오기: {api_time:.2f}초")
        logging.info(f"   노드 변환: {conversion_time:.2f}초")
        logging.info(f"   HTML 생성: {generation_time:.2f}초")
        logging.info(
            f"   총 시간: {api_time + conversion_time + generation_time:.2f}초"
        )
        logging.info(f"   처리된 노드: {stats['nodes_processed']}개")
        logging.info(f"   인라인된 그룹: {stats['groups_inlined']}개")
    except Exception as e:
        logging.error(f"{Fore.RED}❌ 벤치마크 오류: {e}{Style.RESET_ALL}")


cli.add_command(convert)
cli.add_command(benchmark)


if __name__ == "__main__":
    cli()
