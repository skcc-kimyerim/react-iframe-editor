import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple

from core.config import get_setting
from figma2code.service.converter_service_abc import ConverterServiceABC
from figma2code.service.figma2html.figma_api_client import FigmaApiClient
from figma2code.service.figma2html.figma_url_parser import parse_figma_url
from figma2code.service.figma2html.html_generator import HtmlGenerator
from figma2code.service.figma2html.json_node_converter import (
    JsonNodeConverter,
)
from figma2code.service.figma2html.utils import (
    get_best_frame_from_page,
    inject_metadata,
    sanitize_filename,
)
from figma2code.service.figma2react.page_generator import make_filename
from figma2code.service.figma2react.react_generator import (
    ReactComponentGenerator,
)

settings = get_setting()


class ConverterService(ConverterServiceABC):
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

    async def convert_react_component(
        self,
        figma_url: str,
        output: str = "output/frontend/components",
        token: Optional[str] = None,
        embed_shapes: bool = True,
    ) -> Tuple[bool, str]:
        """
        Figma의 특정 노드(또는 대표 프레임)를 기반으로 단일 React TSX 컴포넌트를 생성하여 저장합니다.

        반환: (성공 여부, 메시지)
        - 성공 시 메시지에는 저장 경로가 포함됩니다.
        """
        try:
            file_key, node_id = parse_figma_url(figma_url)
            if not file_key:
                return (
                    False,
                    "잘못된 Figma URL입니다. 올바른 Figma 디자인 URL을 제공해주세요.",
                )

            api_client = FigmaApiClient(token)
            html_generator = HtmlGenerator(api_client=api_client)

            raw_nodes, _ = await self._fetch_figma_data(
                api_client, html_generator, file_key, node_id, embed_shapes
            )
            if not raw_nodes:
                return False, "Figma 데이터를 가져오는데 실패했습니다"

            first_node = raw_nodes[0]

            generator = ReactComponentGenerator()

            # 선택 영역 유사도 판별 → similar/new 분리
            ok, selection = await generator.find_similar_component_in_selection(
                selection_document=first_node,
                guide_md_path="./output/frontend/COMPONENTS_GUIDE.md",
                filter_components=True,
                concurrency=5,
            )
            if not ok:
                return False, f"유사도 판별 실패: {selection}"

            ok2, grouped = generator._is_similar_component(selection)
            if not ok2:
                return False, f"분류 실패: {grouped}"

            similar_items: List[Dict[str, Any]] = grouped.get("similar", [])  # type: ignore
            new_items: List[Dict[str, Any]] = grouped.get("new", [])  # type: ignore

            output_abs = os.path.abspath(output)
            os.makedirs(output_abs, exist_ok=True)

            results_summary: Dict[str, Any] = {
                "similar": [],
                "new": [],
            }

            async def generate_one(item: Dict[str, Any]) -> Dict[str, Any]:
                node = item.get("__component") or first_node
                name = (
                    str(node.get("name", "Component"))
                    if isinstance(node, dict)
                    else "Component"
                )
                generator.component_name = generator._sanitize_component_name(name)
                # 동일 파일명이 존재하면 사전에 삭제하여 덮어쓰기 보장
                try:
                    target_path = os.path.join(
                        output_abs, f"{generator.component_name}.tsx"
                    )
                    if os.path.exists(target_path):
                        os.remove(target_path)
                except Exception:
                    pass
                decision = item.get("decision") or {}
                index_val = (
                    decision.get("index") if isinstance(decision, dict) else None
                )

                # similar: 참조 코드 포함해서 생성 시도
                ok3 = False
                msg = ""
                if isinstance(index_val, int) and index_val != -1:
                    # 유사한 카탈로그 이름으로 로컬 컴포넌트 파일을 찾아 참조
                    ref_sources: Dict[str, str] = {}
                    try:
                        catalog_name = str(decision.get("name", "")).strip()
                        # output/components 폴더에서 비슷한 이름의 파일을 탐색
                        components_dir = output_abs
                        if os.path.isdir(components_dir):
                            for fname in os.listdir(components_dir):
                                if not fname.lower().endswith(".tsx"):
                                    continue
                                base = os.path.splitext(fname)[0].lower()
                                if catalog_name and catalog_name.replace(
                                    "-", ""
                                ).lower() in base.replace("-", ""):
                                    fpath = os.path.join(components_dir, fname)
                                    with open(fpath, "r", encoding="utf-8") as rf:
                                        ref_sources[fname] = rf.read()
                    except Exception:
                        pass

                    if ref_sources:
                        ok3, msg = (
                            await generator._generate_react_component_with_reference(
                                node, output_abs, ref_sources
                            )
                        )
                    else:
                        ok3, msg = await generator._generate_react_component(
                            node, output_abs
                        )
                else:
                    # new: 일반 생성
                    ok3, msg = await generator._generate_react_component(
                        node, output_abs
                    )
                return {
                    "nodeName": item.get("nodeName", name),
                    "componentName": generator.component_name,
                    "ok": ok3,
                    "message": msg,
                    "decision": item.get("decision"),
                }

            for item in similar_items:
                result = await generate_one(item)
                results_summary["similar"].append(result)

            for item in new_items:
                result = await generate_one(item)
                results_summary["new"].append(result)

            overall_ok = any(r.get("ok") for r in results_summary["similar"]) or any(
                r.get("ok") for r in results_summary["new"]
            )

            try:
                message = json.dumps(results_summary, ensure_ascii=False, indent=2)
            except Exception:
                message = str(results_summary)
            return overall_ok, message
        except ValueError as e:
            logging.error(f"설정 오류: {e}")
            return False, f"설정 오류: {e}"
        except Exception as e:
            logging.error(f"컴포넌트 생성 중 오류: {e}")
            return False, f"컴포넌트 생성 중 오류: {e}"

    async def component_similarity(
        self,
        figma_url: str,
        token: Optional[str] = None,
        embed_shapes: bool = True,
        guide_md_path: Optional[str] = "./output/frontend/COMPONENTS_GUIDE.md",
    ) -> Tuple[bool, str]:
        """
        Figma의 특정 노드에 대해 기존 컴포넌트 가이드와의 유사도를 판별합니다.
        결과는 JSON 문자열 형태로 반환합니다.
        """
        try:
            file_key, node_id = parse_figma_url(figma_url)
            if not file_key:
                return (
                    False,
                    "잘못된 Figma URL입니다. 올바른 Figma 디자인 URL을 제공해주세요.",
                )

            api_client = FigmaApiClient(token)
            html_generator = HtmlGenerator(api_client=api_client)

            raw_nodes, _ = await self._fetch_figma_data(
                api_client, html_generator, file_key, node_id, embed_shapes
            )
            if not raw_nodes:
                return False, "Figma 데이터를 가져오는데 실패했습니다"

            first_node = raw_nodes[0]

            generator = ReactComponentGenerator()
            ok, results = await generator.find_similar_component_in_selection(
                selection_document=first_node,
                guide_md_path=guide_md_path or "./output/frontend/COMPONENTS_GUIDE.md",
                filter_components=True,
                concurrency=5,
            )
            if not ok:
                return False, str(results)

            # 출력에는 results만 포함하고, components는 제외
            payload = results.get("results", results)
            try:
                message = json.dumps(payload, ensure_ascii=False, indent=2)
            except Exception:
                message = str(payload)
            return True, message
        except ValueError as e:
            logging.error(f"설정 오류: {e}")
            return False, f"설정 오류: {e}"
        except Exception as e:
            logging.error(f"유사도 판단 중 오류: {e}")
            return False, f"유사도 판단 중 오류: {e}"

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
        Figma 디자인을 기반으로 HTML/CSS를 생성하고, LLM을 사용해 완전한 TSX 페이지를 생성하여 저장합니다.

        - HTML/CSS는 output 디렉토리에 저장합니다.
        - TSX 페이지는 pages 디렉토리에 저장합니다(미지정 시 기본 경로 사용).

        반환: (성공 여부, 메시지)
        - 성공 시 메시지에는 TSX 저장 경로가 포함됩니다.
        """
        try:
            file_key, node_id = parse_figma_url(figma_url)
            if not file_key:
                return (
                    False,
                    "잘못된 Figma URL입니다. 올바른 Figma 디자인 URL을 제공해주세요.",
                )

            api_client = FigmaApiClient(token)
            json_converter = JsonNodeConverter()
            html_generator = HtmlGenerator(api_client=api_client)

            raw_nodes, node_name = await self._fetch_figma_data(
                api_client, html_generator, file_key, node_id, embed_shapes
            )
            if not raw_nodes:
                return False, "Figma 데이터를 가져오는데 실패했습니다"

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

            html_settings = {
                "embedVectors": True,
                "embedImages": True,
                "embedShapes": embed_shapes,
                "htmlGenerationMode": "html",
            }
            html_generator.settings = html_settings
            result = html_generator.html_main(processed_nodes, is_preview=False)

            html_code = result.get("html", "")
            css_code = result.get("css", "")

            # HTML/CSS 저장 (로그 및 경로 안내 목적)
            save_ok, save_msg = self._save_output_files(
                html_code, css_code, node_name, output, conversion_stats
            )
            if not save_ok:
                return False, save_msg

            # 페이지 TSX 프롬프트 구성 (PageGenerator의 로직을 서비스에 맞게 inline 구성)
            components_dir = os.path.abspath(components) if components else None

            component_list_str = ""
            component_docs = ""
            mapping_rules = ""
            usage_examples = ""

            if components_dir and os.path.exists(components_dir):
                try:
                    component_files = [
                        f for f in os.listdir(components_dir) if f.endswith(".tsx")
                    ]
                except Exception:
                    component_files = []

                component_list = [f[:-4] for f in component_files]
                component_list_str = ", ".join(component_list)

                docs_blocks: List[str] = []
                for filename in component_files:
                    path = os.path.join(components_dir, filename)
                    try:
                        with open(path, "r", encoding="utf-8") as f:
                            code = f.read()

                        interfaces = re.findall(
                            r"(interface [A-Za-z0-9_]+(?:Props)?\s*\{[\s\S]*?\n\})",
                            code,
                        )
                        types = re.findall(
                            r"(type [A-Za-z0-9_]+(?:Props)?\s*=\s*\{[\s\S]*?\n\})",
                            code,
                        )
                        all_definitions = interfaces + types

                        if all_definitions:
                            full_docs = "\n".join(all_definitions)
                            docs_blocks.append(f"[{filename}]\n{full_docs}\n")
                        else:
                            match = re.search(
                                r"(function [A-Za-z0-9_]+\([\s\S]+?\))",
                                code,
                            )
                            if match:
                                docs_blocks.append(f"[{filename}]\n{match.group(1)}\n")
                            else:
                                lines = code.splitlines()
                                docs_blocks.append(
                                    f"[{filename}]\n" + "\n".join(lines[:40]) + "\n"
                                )
                    except Exception as e:
                        docs_blocks.append(f"[{filename}]\n(문서 추출 실패: {e})\n")

                component_docs = "[components props/type docs]\n" + "\n".join(
                    docs_blocks
                )

                components_dir_name = os.path.basename(components_dir)

                mapping_rules = (
                    "아래 HTML 구조에서 class명, 텍스트, 계층, placeholder, label 등을 참고해서 "
                    f"{components_dir_name}/에 이미 존재하는 컴포넌트로 적극적으로 매핑해줘.\n"
                    "매핑 규칙 예시:\n"
                    "- class에 'button'이 포함되어 있고, 내부 텍스트가 'confirm', 'Send message' 등인 경우: Button 컴포넌트로 대체\n"
                    "- class에 'field', 'input'이 포함되어 있고, 내부에 'Email', 'Password' 등 텍스트가 있으면: Input 컴포넌트로 대체\n"
                    "- class에 'textarea'가 포함되어 있고, 내부에 'Type your message here' 등 placeholder가 있으면: Textarea 컴포넌트로 대체\n"
                    "이외에도, label/placeholder/텍스트/계층 정보를 적극적으로 활용해서 컴포넌트로 매핑해줘.\n"
                    f"import는 반드시 {components_dir_name}/에서 하고, 나머지는 styled-components로 만들어도 돼.\n"
                )

                usage_examples = (
                    "각 컴포넌트는 placeholder, value, onChange, type 등 props를 적극적으로 활용해줘.\n"
                    "중요: onChange는 (value: string) => void 타입이므로 e.target.value 대신 value를 직접 사용해줘.\n"
                    "Button은 onClick 등 이벤트 핸들러도 추가해줘.\n"
                    "필요하다면 useState, useCallback 등 React 훅을 사용해서 state와 이벤트 핸들러도 구현해.\n"
                    "예시:\n"
                    '  <Input placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} type="email" />\n'
                    "  <Button onClick={handleClick}>confirm</Button>\n"
                    '  <Textarea placeholder="Type your message here" value={message} onChange={(e) => setMessage(e.target.value)} />\n'
                    "이 코드는 실제로 동작하는 React 페이지여야 하며, 단순한 시각적 mockup이 아니어야 해.\n"
                )

                components_dir_name_for_prompt = os.path.basename(components_dir)
                prompt = (
                    "아래는 Figma에서 추출한 HTML/CSS입니다.\n"
                    f"아래 컴포넌트들은 {components_dir_name_for_prompt}/에 이미 존재하니, 반드시 import해서 적극 활용해줘: [{component_list_str}]\n"
                    f"import 할 때는 반드시 각각 개별적으로 import 해야 합니다:\n"
                    f"예시: import NavigationMenu from '../{components_dir_name_for_prompt}/NavigationMenu';\n"
                    f"절대 import {{ ... }} from '{components_dir_name_for_prompt}' 형태로 하지 마세요.\n"
                    f"{component_docs}"
                    f"{mapping_rules}"
                    f"{usage_examples}"
                    "실제 Figma와 동일한 TSX(React) 페이지를 완성해줘.\n"
                    "중요: ```tsx 같은 마크다운 코드블록을 절대 포함하지 마세요. 순수한 TSX 코드만 출력하세요.\n"
                    "중요: 무조건 figma와 동일하게 만들어지는게 중요합니다. 무조건 디자인 따라서 만들어야 합니다.\n"
                    f"HTML:\n{html_code}\n"
                    f"CSS:\n{css_code}\n"
                )
            else:
                prompt = (
                    "아래는 Figma에서 추출한 HTML/CSS입니다.\n"
                    "이 HTML/CSS를 바탕으로 완전한 React TypeScript 페이지를 생성해주세요.\n"
                    "중요 사항:\n"
                    "- TypeScript + styled-components 사용\n"
                    "- HTML 구조를 정확히 React 컴포넌트로 변환\n"
                    "- CSS 스타일을 styled-components로 변환\n"
                    "- useState, useCallback 등 필요한 React 훅 사용\n"
                    "- 실제로 동작하는 페이지로 만들어주세요\n"
                    "- ```tsx 같은 마크다운 코드블록을 절대 포함하지 마세요. 순수한 TSX 코드만 출력하세요.\n"
                    "- 무조건 figma와 동일하게 만들어지는게 중요합니다. 무조건 디자인 따라서 만들어야 합니다.\n"
                    f"HTML:\n{html_code}\n"
                    f"CSS:\n{css_code}\n"
                )

            react_generator = ReactComponentGenerator()
            try:
                tsx_code = (
                    await react_generator._generate_react_from_html_css_with_prompt(
                        prompt
                    )
                )
            except Exception as e:
                return False, f"TSX 코드 생성 실패: {e}"

            tsx_filename = make_filename(node_name)
            if pages:
                pages_dir = os.path.abspath(pages)
            else:
                pages_dir = os.path.abspath(
                    os.path.join(os.path.dirname(__file__), "output/frontend")
                )

            os.makedirs(pages_dir, exist_ok=True)
            tsx_path = os.path.join(pages_dir, tsx_filename)
            try:
                with open(tsx_path, "w", encoding="utf-8") as f:
                    f.write(tsx_code)
            except Exception as e:
                return False, f"TSX 파일 저장 중 오류: {e}"

            logging.info(f"HTML/CSS 출력 디렉토리: {os.path.abspath(output)}")
            logging.info(f"TSX 페이지 저장 경로: {tsx_path}")
            return True, f"TSX 페이지 저장 완료: {tsx_path}"

        except ValueError as e:
            logging.error(f"설정 오류: {e}")
            return False, f"설정 오류: {e}"
        except Exception as e:
            logging.error(f"페이지 생성 중 오류: {e}")
            return False, f"페이지 생성 중 오류: {e}"

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
