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

from figma2code.chat.service.figma2html.figma_api_client import FigmaApiClient
from figma2code.chat.service.figma2html.figma_url_parser import parse_figma_url
from figma2code.chat.service.figma2html.html_generator import HtmlGenerator
from figma2code.chat.service.figma2html.json_node_converter import JsonNodeConverter
from figma2code.chat.service.figma2html.utils import (
    get_best_frame_from_page,
    inject_metadata,
    sanitize_filename,
)

from .page_generator import (
    PageGenerator,
    make_filename,
)
from .react_generator import ReactComponentGenerator

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
        self, figma_url: str, output_dir: str = "output"
    ) -> Tuple[bool, str, str, str, str]:
        try:
            logging.info(
                f"{Fore.BLUE}🔄 Figma URL 파싱 중: {figma_url}{Style.RESET_ALL}"
            )
            file_key, node_id = parse_figma_url(figma_url)

            if not file_key:
                return (
                    False,
                    "잘못된 Figma URL입니다. 올바른 Figma 디자인 URL을 제공해주세요.",
                    "",
                    "",
                    "",
                )

            logging.debug(f"{Fore.BLUE}📂 파일 키: {file_key}{Style.RESET_ALL}")
            if node_id:
                logging.debug(f"{Fore.BLUE}🎯 노드 ID: {node_id}{Style.RESET_ALL}")

            # 데이터 가져오기
            raw_nodes, node_name = self._fetch_figma_data(file_key, node_id)
            if not raw_nodes:
                return False, "Figma 데이터를 가져오는데 실패했습니다", "", ""

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
                return False, "처리된 노드가 없습니다", "", ""

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
            success, message = self._save_output_files(
                html_content, css_content, node_name, output_dir, conversion_stats
            )
            return success, message, html_content, css_content, node_name

        except Exception as e:
            return False, f"변환 중 오류 발생: {str(e)}", "", ""

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
        return raw_nodes, node_name

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


@click.group()
def cli() -> None:
    """Figma to Code - 고급 처리로 Figma 디자인을 HTML/CSS로 변환"""
    pass


@cli.command()
@click.argument("figma_url")
@click.option("--output", "-o", default="output", help="생성된 파일의 출력 디렉토리")
@click.option(
    "--token", "-t", help="Figma API 토큰 (또는 FIGMA_API_TOKEN 환경변수 설정)"
)
def convert(figma_url: str, output: str, token: Optional[str]) -> None:
    """
    Figma 디자인을 HTML/CSS로 변환

    FIGMA_URL: Figma 디자인 URL (예: https://www.figma.com/design/...)
    """
    try:
        converter = FigmaToCode(token)
        converter.api_client.clear_response_cache()
        success, message, _, _, _ = converter.convert_from_url(figma_url, output)

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


@cli.command()
@click.argument("figma_url")
@click.option(
    "--output",
    "-o",
    default="output/frontend/components",
    help="React 컴포넌트 출력 디렉토리",
)
@click.option(
    "--token", "-t", help="Figma API 토큰 (또는 FIGMA_API_TOKEN 환경변수 설정)"
)
def convert_react(figma_url: str, output: str, token: Optional[str]) -> None:
    """
    Figma 디자인을 React TSX 컴포넌트로 변환 (단일 노드)

    FIGMA_URL: Figma 디자인 URL (예: https://www.figma.com/design/...)
    """
    try:
        logging.info(
            f"{Fore.BLUE}🔄 Figma URL에서 React 컴포넌트 생성 중...{Style.RESET_ALL}"
        )

        # 1. Figma 데이터 가져오기
        converter = FigmaToCode(token)
        file_key, node_id = parse_figma_url(figma_url)

        if not file_key:
            logging.error(f"{Fore.RED}❌ 잘못된 Figma URL입니다{Style.RESET_ALL}")
            sys.exit(1)

        logging.info(f"{Fore.BLUE}📂 파일 키: {file_key}{Style.RESET_ALL}")
        if node_id:
            logging.info(f"{Fore.BLUE}🎯 노드 ID: {node_id}{Style.RESET_ALL}")

        # 2. 노드 데이터 가져오기
        raw_nodes, _ = converter._fetch_figma_data(file_key, node_id)
        if not raw_nodes:
            logging.error(
                f"{Fore.RED}❌ Figma 데이터를 가져오는데 실패했습니다{Style.RESET_ALL}"
            )
            sys.exit(1)

        logging.info(f"{Fore.GREEN}✅ Figma 데이터 가져오기 성공{Style.RESET_ALL}")

        # 3. React 컴포넌트 생성
        logging.info(f"{Fore.YELLOW}🔄 React 컴포넌트 생성 중...{Style.RESET_ALL}")
        generator = ReactComponentGenerator()

        # 첫 번째 노드를 사용해서 컴포넌트 생성
        first_node = raw_nodes[0]
        success, message = generator.generate_component(first_node, output)

        if success:
            logging.info(f"{Fore.GREEN}🎉 {message}{Style.RESET_ALL}")
            logging.info(
                f"{Fore.CYAN}💡 생성된 컴포넌트를 사용하려면:{Style.RESET_ALL}"
            )
            logging.info(
                f"   import {generator.component_name} from './{output}/{generator.component_name}';"
            )
            logging.info(
                f'   <{generator.component_name} variant="Default" label="버튼 텍스트" />'
            )
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
        print(f"{Fore.RED}❌ 예상치 못한 오류: {e}{Style.RESET_ALL}")
        sys.exit(1)


@cli.command()
@click.argument("figma_url")
@click.option(
    "--output",
    "-o",
    default="output/frontend/components",
    help="React 컴포넌트 출력 디렉토리",
)
@click.option(
    "--token", "-t", help="Figma API 토큰 (또는 FIGMA_API_TOKEN 환경변수 설정)"
)
@click.option(
    "--filter-components",
    "-f",
    is_flag=True,
    help="COMPONENT/INSTANCE 타입만 필터링해서 처리",
)
def convert_react_selection(
    figma_url: str, output: str, token: Optional[str], filter_components: bool
) -> None:
    """
    Figma 노드 선택에 있는 모든 컴포넌트를 React TSX 컴포넌트로 변환

    FIGMA_URL: Figma 디자인 URL (node-id 포함)
    """
    try:
        logging.info(
            f"{Fore.BLUE}🔄 Figma 노드 선택의 모든 컴포넌트를 React로 변환 중...{Style.RESET_ALL}"
        )

        # 1. Figma URL 파싱
        converter = FigmaToCode(token)
        file_key, node_id = parse_figma_url(figma_url)

        if not file_key:
            logging.error(f"{Fore.RED}❌ 잘못된 Figma URL입니다{Style.RESET_ALL}")
            sys.exit(1)

        if not node_id:
            logging.error(
                f"{Fore.RED}❌ node-id가 필요합니다. 특정 노드를 선택해주세요{Style.RESET_ALL}"
            )
            sys.exit(1)

        logging.info(f"{Fore.BLUE}📂 파일 키: {file_key}{Style.RESET_ALL}")
        logging.info(f"{Fore.BLUE}🎯 노드 ID: {node_id}{Style.RESET_ALL}")

        # 2. 특정 노드 데이터 가져오기
        logging.info(
            f"{Fore.YELLOW}🔄 선택된 노드 데이터 가져오는 중...{Style.RESET_ALL}"
        )
        raw_nodes, node_name = converter._fetch_figma_data(file_key, node_id)
        if not raw_nodes:
            logging.error(
                f"{Fore.RED}❌ Figma 노드 데이터를 가져오는데 실패했습니다{Style.RESET_ALL}"
            )
            sys.exit(1)

        logging.info(f"{Fore.GREEN}✅ Figma 노드 데이터 가져오기 성공{Style.RESET_ALL}")
        logging.info(f"{Fore.CYAN}📝 선택된 노드: '{node_name}'{Style.RESET_ALL}")

        # 3. 선택된 노드에서 모든 컴포넌트 추출
        selected_node = raw_nodes[0]
        all_nodes = _extract_all_nodes_from_selection(selected_node, filter_components)

        if not all_nodes:
            logging.warning(
                f"{Fore.YELLOW}⚠️  처리할 컴포넌트가 없습니다{Style.RESET_ALL}"
            )
            sys.exit(0)

        logging.info(
            f"{Fore.CYAN}🎯 찾은 컴포넌트 수: {len(all_nodes)}개{Style.RESET_ALL}"
        )

        # 4. 각 컴포넌트별로 React 컴포넌트 생성
        generator = ReactComponentGenerator()
        success_count = 0
        failure_count = 0

        for i, node in enumerate(all_nodes, 1):
            node_name = node.get("name", f"Component_{i}")
            node_type = node.get("type", "UNKNOWN")

            logging.info(
                f"{Fore.BLUE}🔄 [{i}/{len(all_nodes)}] {node_type}: '{node_name}' 처리 중...{Style.RESET_ALL}"
            )

            # 메타데이터 주입
            inject_metadata(node, file_key, node_id)

            try:
                success, message = generator.generate_component(node, output)
                if success:
                    logging.info(
                        f"{Fore.GREEN}✅ {generator.component_name} 생성 완료{Style.RESET_ALL}"
                    )
                    success_count += 1
                else:
                    logging.error(
                        f"{Fore.RED}❌ {node_name} 생성 실패: {message}{Style.RESET_ALL}"
                    )
                    failure_count += 1
            except Exception as e:
                logging.error(
                    f"{Fore.RED}❌ {node_name} 처리 중 오류: {e}{Style.RESET_ALL}"
                )
                failure_count += 1

        # 5. 결과 요약
        logging.info(f"\n{Fore.GREEN}🎉 선택 노드 변환 완료!{Style.RESET_ALL}")
        logging.info(
            f"{Fore.CYAN}📊 성공: {success_count}개, 실패: {failure_count}개{Style.RESET_ALL}"
        )
        logging.info(f"{Fore.CYAN}📁 출력 디렉토리: {output}{Style.RESET_ALL}")

        if success_count > 0:
            logging.info(
                f"\n{Fore.YELLOW}💡 생성된 컴포넌트 사용 예시:{Style.RESET_ALL}"
            )
            logging.info(
                f"   import {{ ComponentName }} from './{output}/ComponentName';"
            )
            logging.info(f"   <ComponentName />")

    except ValueError as e:
        print(f"{Fore.RED}❌ 설정 오류: {e}{Style.RESET_ALL}")
        print(
            f"{Fore.YELLOW}💡 FIGMA_API_TOKEN 환경변수를 설정하거나 --token 옵션을 사용하세요{Style.RESET_ALL}"
        )
        sys.exit(1)
    except Exception as e:
        print(f"{Fore.RED}❌ 예상치 못한 오류: {e}{Style.RESET_ALL}")
        sys.exit(1)


@cli.command()
@click.argument("figma_url")
def info(figma_url: str) -> None:
    """Figma 디자인 URL 정보 확인"""
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
@click.argument("figma_url")
@click.option("--token", "-t", help="Figma API 토큰")
def benchmark(figma_url: str, token: Optional[str]) -> None:
    """변환 성능 벤치마크"""
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


@cli.command()
@click.argument("figma_url")
@click.option("--output", "-o", default="output", help="HTML/CSS 파일의 출력 디렉토리")
@click.option("--pages", "-p", help="TSX 페이지 파일의 출력 디렉토리")
@click.option(
    "--token", "-t", help="Figma API 토큰 (또는 FIGMA_API_TOKEN 환경변수 설정)"
)
@click.option(
    "--components",
    "-c",
    help="컴포넌트 디렉토리 경로 (기본값: frontend/src/test-components)",
)
def create_page(
    figma_url: str,
    output: str,
    pages: Optional[str],
    token: Optional[str],
    components: Optional[str],
) -> None:
    """
    Figma 파일의 모든 페이지를 LLM 기반 tsx 파일로 변환

    HTML/CSS는 --output 디렉토리에, TSX 페이지는 --pages 디렉토리에 저장됩니다.
    """
    try:
        converter = FigmaToCode(token)
        generator = PageGenerator(components_dir=components)

        # HTML/CSS 생성 (기본 output 디렉토리에 저장)
        success, message, html_code, css_code, node_name = converter.convert_from_url(
            figma_url, output
        )
        if success:
            logging.info(
                f"{Fore.GREEN}🎉 HTML/CSS 생성 완료: {message}{Style.RESET_ALL}"
            )
        else:
            logging.error(
                f"{Fore.RED}❌ HTML/CSS 생성 실패: {message}{Style.RESET_ALL}"
            )
            sys.exit(1)

        # TSX 페이지 생성
        success, tsx_code = generator.generate_layout_with_llm(
            html_code, css_code, output
        )
        if success:
            # TSX 파일명 생성
            tsx_filename = make_filename(node_name)

            # pages 디렉토리 결정
            if pages:
                # 사용자가 지정한 pages 디렉토리 사용
                pages_dir = os.path.abspath(pages)
            else:
                # 기본 pages 디렉토리 사용
                pages_dir = os.path.abspath(
                    os.path.join(os.path.dirname(__file__), "output/frontend")
                )

            os.makedirs(pages_dir, exist_ok=True)
            tsx_path = os.path.join(pages_dir, tsx_filename)
            with open(tsx_path, "w", encoding="utf-8") as f:
                f.write(tsx_code)
            logging.info(
                f"{Fore.GREEN}✅ TSX 페이지 저장 완료: {tsx_path}{Style.RESET_ALL}"
            )
            logging.info(f"{Fore.CYAN}📁 HTML/CSS: {output}{Style.RESET_ALL}")
            logging.info(f"{Fore.CYAN}📁 TSX 페이지: {pages_dir}{Style.RESET_ALL}")
        else:
            logging.error(
                f"{Fore.RED}❌ TSX 코드 생성 실패: {tsx_code}{Style.RESET_ALL}"
            )
    except ValueError as e:
        print(f"{Fore.RED}❌ 설정 오류: {e}{Style.RESET_ALL}")
        print(
            f"{Fore.YELLOW}💡 FIGMA_API_TOKEN 환경변수를 설정하거나 --token 옵션을 사용하세요{Style.RESET_ALL}"
        )
        print(
            f"{Fore.YELLOW}   토큰 발급: https://www.figma.com/developers/api#access-tokens{Style.RESET_ALL}"
        )
        sys.exit(1)


def _extract_all_nodes_from_selection(
    node: Dict[str, Any], filter_components: bool = False
) -> List[Dict[str, Any]]:
    """
    특정 노드에서 모든 처리 가능한 컴포넌트를 추출

    Args:
        node: Figma 노드 데이터
        filter_components: True면 COMPONENT/INSTANCE만 필터링

    Returns:
        추출된 컴포넌트 리스트
    """

    def _collect_components(
        node: Dict[str, Any],
        collected: List[Dict[str, Any]],
        is_nested_component: bool = False,
    ) -> None:
        node_type = node.get("type")
        node_name = node.get("name", "")

        # 노드 타입 및 이름 기반 필터링
        if filter_components:
            # 컴포넌트 타입이면서 중첩되지 않은 경우만
            if node_type in ["COMPONENT", "INSTANCE", "COMPONENT_SET"]:
                if not is_nested_component:  # 최상위 컴포넌트만 수집
                    collected.append(node.copy())
                    return  # 자식 탐색 중단 (중복 방지)
        else:
            # 처리 가능한 모든 타입
            if node_type in [
                "COMPONENT",
                "INSTANCE",
                "COMPONENT_SET",
            ]:
                # 의미있는 크기를 가진 노드만
                width = node.get("width", 0)
                height = node.get("height", 0)
                if width > 10 and height > 10:  # 최소 크기 조건
                    collected.append(node.copy())

        # 자식 노드 재귀 처리
        children = node.get("children", [])
        for child in children:
            _collect_components(child, collected, False)

    collected_components = []
    _collect_components(node, collected_components, False)

    # 중복 제거 및 정렬 (크기 기준 내림차순)
    unique_components = []
    seen_names = set()

    for component in collected_components:
        component_name = component.get("name", "")
        if component_name and component_name not in seen_names:
            seen_names.add(component_name)
            unique_components.append(component)

    # 크기 기준으로 정렬 (큰 것부터)
    unique_components.sort(
        key=lambda c: c.get("width", 0) * c.get("height", 0), reverse=True
    )

    return unique_components


if __name__ == "__main__":
    cli()
