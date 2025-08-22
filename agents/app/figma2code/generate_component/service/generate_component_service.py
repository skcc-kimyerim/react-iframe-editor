import json
import logging
import os
from typing import Any, Dict, List, Optional, Tuple

from core.config import get_setting
from figma2code.generate_component.service.generate_component_service_abc import (
    GenerateComponentServiceABC,
)

from figma2code.common.figma2html.figma_api_client import FigmaApiClient
from figma2code.common.figma2html.figma_url_parser import parse_figma_url
from figma2code.common.figma2html.html_generator import HtmlGenerator
from figma2code.common.figma2html.utils import get_best_frame_from_page, inject_metadata
from figma2code.common.figma2react.react_generator import ReactComponentGenerator

settings = get_setting()


class GenerateComponentService(GenerateComponentServiceABC):
    def __init__(self):
        pass

    async def generate(
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

    async def find_similar(
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


# FastAPI Depends 용 DI 팩토리
def get_generate_component_service() -> GenerateComponentService:
    return GenerateComponentService()
