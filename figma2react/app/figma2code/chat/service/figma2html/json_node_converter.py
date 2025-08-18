"""
JSON Node Converter
Figma 노드를 JSON 형식으로 변환하는 고급 컨버터
"""

import json
import logging
import math
from typing import Any, Dict, List, Optional, Tuple, Union

from .icon_detection import is_likely_icon


class JsonNodeConverter:
    """Figma 노드를 JSON 형식으로 변환하는 고급 컨버터"""

    def __init__(self):
        self.node_name_counters: Dict[str, int] = {}
        self.css_collection: Dict[str, Dict[str, Any]] = {}
        self.performance_counters = {
            "nodes_processed": 0,
            "nodes_skipped": 0,
            "groups_inlined": 0,
        }

    def reset_counters(self) -> None:
        """새로운 변환을 위한 카운터 초기화"""
        self.node_name_counters.clear()
        self.css_collection.clear()
        self.performance_counters = {
            "nodes_processed": 0,
            "nodes_skipped": 0,
            "groups_inlined": 0,
        }

    def nodes_to_json(
        self, nodes: List[Dict[str, Any]], settings: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Figma 노드를 부모 참조가 추가된 JSON 형식으로 변환

        Args:
            nodes: 변환할 Figma 노드들
            settings: 변환 설정

        Returns:
            (부모 참조가 있는 노드의 JSON 표현, 성능 통계)
        """
        self.reset_counters()
        if settings is None:
            settings = {}

        result = []

        for node in nodes:
            # 그룹 처리를 위한 노드 변환
            node_doc = self._prepare_node_for_processing(node)

            processed_node = self._process_node_pair(
                json_node=node_doc,
                settings=settings,
                parent_node=None,
                parent_cumulative_rotation=0,
            )

            if processed_node is not None:
                if isinstance(processed_node, list):
                    # 인라인된 그룹의 경우 배열 반환 시 모든 노드 추가
                    result.extend(processed_node)
                else:
                    # 단일 노드 반환 시 직접 추가
                    result.append(processed_node)

        logging.debug(
            f"[JsonNodeConverter] 처리된 노드: {self.performance_counters['nodes_processed']}개, "
            f"건너뛴 노드: {self.performance_counters['nodes_skipped']}개, "
            f"인라인된 그룹: {self.performance_counters['groups_inlined']}개"
        )

        return result, self.get_performance_stats()

    def _prepare_node_for_processing(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """처리를 위한 노드 준비"""
        node_doc = node.copy()
        node_cumulative_rotation = 0

        # GROUP을 FRAME으로 변환
        if node.get("type") == "GROUP":
            node_doc["type"] = "FRAME"

            # 자식에 대한 회전 처리
            if "rotation" in node_doc and node_doc["rotation"]:
                node_cumulative_rotation = -node_doc["rotation"] * (180 / math.pi)
                node_doc["rotation"] = 0

        return node_doc

    def _process_node_pair(
        self,
        json_node: Dict[str, Any],
        settings: Dict[str, Any],
        parent_node: Optional[Dict[str, Any]] = None,
        parent_cumulative_rotation: float = 0,
    ) -> Union[Dict[str, Any], List[Dict[str, Any]], None]:
        """
        노드 쌍 처리 - FigmaToCode의 processNodePair 패턴

        Args:
            json_node: 처리할 JSON 노드
            settings: 변환 설정
            parent_node: 부모 노드 (선택사항)
            parent_cumulative_rotation: 부모의 누적 회전 (기본값: 0)

        Returns:
            처리된 노드, 노드 배열, 또는 None
        """
        # 기본 가시성 확인
        if not json_node.get("visible", True):
            self.performance_counters["nodes_skipped"] += 1
            return None

        # 노드 타입 확인
        node_type = json_node.get("type")
        if not node_type:
            self.performance_counters["nodes_skipped"] += 1
            return None

        logging.debug(
            f"[JsonNodeConverter] Node process start '{json_node.get('name', 'unknown')}' with parent '{parent_node.get('name', 'unknown') if parent_node else 'None'}'"
        )

        # 고유 이름 보장
        self._ensure_unique_name(json_node)

        # 텍스트 노드 처리
        if node_type == "TEXT":
            self._process_text_node(json_node, settings)

        # 크기 및 위치 처리
        # 디버깅: 부모-자식 관계 확인
        node_name = json_node["uniqueName"]
        parent_name = parent_node["uniqueName"] if parent_node else "None"
        logging.debug(
            f"[PARENT DEBUG] Processing '{node_name}' with parent '{parent_name}'"
        )

        self._process_size_and_position(json_node, parent_node)

        # 레이아웃 정보 처리
        self._process_layout_info(json_node)

        # 자식 노드 처리
        logging.debug(
            f"[CHILDREN DEBUG] Processing '{json_node['uniqueName']}' with children"
        )
        children = json_node.get("children", [])
        if children:
            processed_children = []

            # 원본 순서 정보 추가
            for i, child in enumerate(children):
                if child:
                    child["_original_order"] = i

            for child in children:
                # 현재 노드의 회전을 누적 회전에 추가
                current_rotation = json_node.get("rotation", 0)
                if current_rotation:
                    current_rotation = current_rotation * (
                        180 / math.pi
                    )  # 라디안에서 도로 변환

                cumulative_rotation = parent_cumulative_rotation + current_rotation

                processed_child = self._process_node_pair(
                    json_node=child,
                    settings=settings,
                    parent_node=json_node,
                    parent_cumulative_rotation=cumulative_rotation,
                )

                if processed_child is not None:
                    if isinstance(processed_child, list):
                        # 인라인된 그룹의 자식들 - 부모 관계 재설정
                        for inlined_child in processed_child:
                            if inlined_child is not None:
                                # 인라인된 자식의 부모를 현재 노드로 재설정
                                original_parent = inlined_child.get("_original_parent")
                                if original_parent:
                                    # 원래 부모 정보가 있으면 사용
                                    logging.debug(
                                        f"[INLINE PARENT] '{inlined_child.get('name', 'unknown')}' originally from '{original_parent.get('name', 'unknown')}', now under '{json_node.get('name', 'unknown')}'"
                                    )

                                self._update_parent_references(inlined_child, json_node)
                                processed_children.append(inlined_child)
                    else:
                        processed_children.append(processed_child)

            json_node["children"] = processed_children

            # 자식 순서 조정 (원본 순서 유지)
            self._adjust_children_order(json_node)

        # 그룹 인라인 처리
        logging.debug(
            f"[FRAME INLINE DEBUG] Processing '{json_node['uniqueName']}' with children"
        )
        if (
            node_type == "FRAME"
            and json_node.get("name", "").strip() == ""
            and len(json_node.get("children", [])) > 0
        ):
            # 빈 이름의 프레임을 그룹으로 인라인
            self.performance_counters["groups_inlined"] += 1

            # 인라인될 자식들에게 메타데이터 추가 (부모 추적용)
            children = json_node.get("children", [])
            for i, child in enumerate(children):
                if child:
                    # 인라인된 노드임을 표시
                    child["_inlined_from"] = json_node.get("name", "unnamed_frame")
                    child["_original_parent"] = json_node
                    # 원본 순서 정보 보존
                    child["_original_order"] = i

                    # 디버깅 로그
                    child_name = child.get("name", "unknown")
                    logging.debug(
                        f"[INLINE DEBUG] '{child_name}' inlined from '{json_node.get('name', 'unnamed')}' with order {i}"
                    )

            return children

        self.performance_counters["nodes_processed"] += 1
        logging.debug(
            f"[JsonNodeConverter] Node process end '{json_node['uniqueName']}'"
        )
        return json_node

    def _ensure_unique_name(self, json_node: Dict[str, Any]) -> None:
        """노드의 고유 이름 보장"""
        base_name = json_node.get("name", "")
        if not base_name:
            node_type = json_node.get("type", "node")
            base_name = node_type.lower()

        # 고유 이름 생성
        count = self.node_name_counters.get(base_name, 0)
        self.node_name_counters[base_name] = count + 1

        if count > 0:
            unique_name = f"{base_name}_{count}"
        else:
            unique_name = base_name

        json_node["uniqueName"] = unique_name

    def _process_text_node(
        self, json_node: Dict[str, Any], settings: Dict[str, Any]
    ) -> None:
        """텍스트 노드 처리"""
        # 텍스트 내용 확인
        characters = json_node.get("characters", "")
        if not characters:
            json_node["characters"] = "텍스트"

        # 스타일 기본값 설정
        if "style" not in json_node:
            json_node["style"] = {}

        style = json_node["style"]

        # 기본 폰트 속성 설정
        if "fontFamily" not in style:
            style["fontFamily"] = "Inter"
        if "fontSize" not in style:
            style["fontSize"] = 14
        if "fontWeight" not in style:
            style["fontWeight"] = 400

        # 색상 정보 처리
        if "fills" in json_node and json_node["fills"]:
            fill = json_node["fills"][0]
            if fill.get("type") == "SOLID" and "color" in fill:
                color = fill["color"]
                # RGB 값을 CSS 형식으로 변환
                r = int(color.get("r", 0) * 255)
                g = int(color.get("g", 0) * 255)
                b = int(color.get("b", 0) * 255)
                style["color"] = f"rgb({r}, {g}, {b})"

    def _process_size_and_position(
        self, json_node: Dict[str, Any], parent_node: Optional[Dict[str, Any]]
    ) -> None:
        """크기 및 위치 처리"""
        # 절대 경계 상자에서 크기 정보 추출
        if "absoluteBoundingBox" in json_node:
            bbox = json_node["absoluteBoundingBox"]
            logging.debug(
                f"[SIZE AND POSITION] Processing '{json_node['uniqueName']}' with parent '{parent_node['uniqueName'] if parent_node else 'None'}'"
            )
            if bbox is None:
                logging.warning(
                    f"[경고] absoluteBoundingBox가 None입니다. node: {json_node.get('name', json_node.get('id', 'unknown'))}"
                )
                bbox = {}
            # 크기 설정
            logging.debug(f"[SIZE AND POSITION] bbox: {bbox}")
            if "width" not in json_node:
                json_node["width"] = bbox.get("width", 0)
            if "height" not in json_node:
                json_node["height"] = bbox.get("height", 0)

            node_name = json_node["uniqueName"]

            # 위치 설정 (부모 상대적)
            if parent_node and "absoluteBoundingBox" in parent_node:
                parent_bbox = parent_node["absoluteBoundingBox"]
                if parent_bbox is None:
                    logging.warning(
                        f"[경고] parent absoluteBoundingBox가 None입니다. parent: {parent_node.get('name', parent_node.get('id', 'unknown'))}"
                    )
                    parent_bbox = {}
                logging.debug(f"[SIZE AND POSITION] parent_bbox: {parent_bbox}")
                json_node["x"] = bbox.get("x", 0) - parent_bbox.get("x", 0)
                json_node["y"] = bbox.get("y", 0) - parent_bbox.get("y", 0)
            elif parent_node:
                logging.warning(
                    f"[경고] Node: '{node_name}' no absolute bounding box in parent node'"
                )
                json_node["x"] = bbox.get("x", 0)
                json_node["y"] = bbox.get("y", 0)
            else:
                logging.warning(f"[경고] Node: '{node_name}' no parent node'")
                json_node["x"] = bbox.get("x", 0)
                json_node["y"] = bbox.get("y", 0)

            logging.debug(
                f"[SIZE AND POSITION] x: {json_node['x']}, y: {json_node['y']}"
            )

        # 회전 처리 - transform rotate 정보만 추가
        if "rotation" in json_node and json_node["rotation"]:
            rotation_degrees = json_node["rotation"] * (180 / math.pi)

            # 위치와 크기는 변경하지 않고 CSS transform 정보만 추가
            json_node["transform"] = {"rotate": rotation_degrees}

            # 디버깅 로그
            logging.debug(
                f"[ROTATION] '{json_node['uniqueName']}' rotation: {rotation_degrees}° - preserving original position x: {json_node.get('x', 0)}, y: {json_node.get('y', 0)}"
            )

    def _is_likely_icon(self, json_node: Dict[str, Any]) -> bool:
        """노드가 아이콘일 가능성 확인"""
        return is_likely_icon(json_node)

    def _process_layout_info(self, json_node: Dict[str, Any]) -> None:
        """레이아웃 정보 처리 - Figma API 스펙 기반"""
        layout_mode = json_node.get("layoutMode", "NONE")

        # 디버깅: layout mode 확인
        node_name = json_node.get("name", "unknown")
        logging.debug(
            f"[JSON CONVERTER DEBUG] Node: '{node_name}' | Layout Mode: '{layout_mode}'"
        )

        # layoutMode 기본값 보장
        if "layoutMode" not in json_node:
            json_node["layoutMode"] = "NONE"
            layout_mode = "NONE"

        # 자동 레이아웃 정보 설정
        if layout_mode != "NONE":
            json_node["isAutoLayout"] = True

            # Auto Layout Frame 속성들 처리
            if layout_mode in ["HORIZONTAL", "VERTICAL"]:
                # Flexbox 기반 auto layout
                self._process_flex_layout_properties(json_node)
            elif layout_mode == "GRID":
                # Grid 기반 auto layout
                self._process_grid_layout_properties(json_node)

            # 공통 auto layout 속성들
            self._process_common_auto_layout_properties(json_node)
        else:
            # 수동 레이아웃 노드
            json_node["isAutoLayout"] = False

        # 위치 지정 방식 설정
        json_node["isRelative"] = layout_mode == "NONE"

        # 자식 요소의 auto layout 속성 처리
        self._process_child_layout_properties(json_node)

    def _process_flex_layout_properties(self, json_node: Dict[str, Any]) -> None:
        """Flexbox 기반 auto layout 속성 처리"""
        # 기본 flex 속성들은 이미 존재하므로 추가 처리 없음
        pass

    def _process_grid_layout_properties(self, json_node: Dict[str, Any]) -> None:
        """Grid 기반 auto layout 속성 처리"""
        # Grid 전용 속성들 확인 및 기본값 설정
        if "gridRowCount" not in json_node:
            json_node["gridRowCount"] = 1
        if "gridColumnCount" not in json_node:
            json_node["gridColumnCount"] = 1
        if "gridRowGap" not in json_node:
            json_node["gridRowGap"] = 0
        if "gridColumnGap" not in json_node:
            json_node["gridColumnGap"] = 0

    def _process_common_auto_layout_properties(self, json_node: Dict[str, Any]) -> None:
        """공통 auto layout 속성 처리"""
        # 패딩 기본값 설정
        for padding in ["paddingLeft", "paddingRight", "paddingTop", "paddingBottom"]:
            if padding not in json_node:
                json_node[padding] = 0

        # 간격 기본값 설정
        if "itemSpacing" not in json_node:
            json_node["itemSpacing"] = 0
        if "counterAxisSpacing" not in json_node:
            json_node["counterAxisSpacing"] = 0

        # 정렬 기본값 설정
        if "primaryAxisAlignItems" not in json_node:
            json_node["primaryAxisAlignItems"] = "MIN"
        if "counterAxisAlignItems" not in json_node:
            json_node["counterAxisAlignItems"] = "MIN"

        # 크기 모드 기본값 설정
        if "primaryAxisSizingMode" not in json_node:
            json_node["primaryAxisSizingMode"] = "AUTO"
        if "counterAxisSizingMode" not in json_node:
            json_node["counterAxisSizingMode"] = "AUTO"

        # 래핑 기본값 설정
        if "layoutWrap" not in json_node:
            json_node["layoutWrap"] = "NO_WRAP"

    def _process_child_layout_properties(self, json_node: Dict[str, Any]) -> None:
        """자식 요소의 auto layout 속성 처리"""
        children = json_node.get("children", [])
        parent_layout_mode = json_node.get("layoutMode", "NONE")

        for child in children:
            # 자식 요소의 auto layout 관련 속성 처리
            if parent_layout_mode != "NONE":
                # layoutAlign 기본값 설정 (auto layout frame의 직접 자식에만 적용)
                if "layoutAlign" not in child:
                    child["layoutAlign"] = "INHERIT"

                # layoutGrow 기본값 설정
                if "layoutGrow" not in child:
                    child["layoutGrow"] = 0

                # layoutSizing 속성들 기본값 설정
                if "layoutSizingHorizontal" not in child:
                    child["layoutSizingHorizontal"] = "FIXED"
                if "layoutSizingVertical" not in child:
                    child["layoutSizingVertical"] = "FIXED"

                # Grid 자식 속성들
                if parent_layout_mode == "GRID":
                    grid_props = [
                        ("gridChildHorizontalAlign", "AUTO"),
                        ("gridChildVerticalAlign", "AUTO"),
                        ("gridRowSpan", 1),
                        ("gridColumnSpan", 1),
                        ("gridColumnAnchorIndex", 0),
                        ("gridRowAnchorIndex", 0),
                    ]
                    for prop, default_value in grid_props:
                        if prop not in child:
                            child[prop] = default_value

    def _update_parent_references(
        self, node: Dict[str, Any], new_parent: Dict[str, Any]
    ) -> None:
        """인라인된 노드의 부모 참조 업데이트"""
        if node is None or new_parent is None:
            return

        # 부모 기준으로 위치 재계산
        if "absoluteBoundingBox" in node and "absoluteBoundingBox" in new_parent:
            node_bbox = node["absoluteBoundingBox"]
            parent_bbox = new_parent["absoluteBoundingBox"]

            if node_bbox and parent_bbox:
                # 새로운 부모 기준으로 상대 좌표 재계산
                node["x"] = node_bbox.get("x", 0) - parent_bbox.get("x", 0)
                node["y"] = node_bbox.get("y", 0) - parent_bbox.get("y", 0)

                # 디버깅 로그
                node_name = node.get("name", "unknown")
                parent_name = new_parent.get("name", "unknown")
                logging.debug(
                    f"[PARENT UPDATE] '{node_name}' parent updated to '{parent_name}' - x: {node['x']}, y: {node['y']}"
                )

        # 자식 노드들도 재귀적으로 처리 (필요한 경우)
        children = node.get("children", [])
        for child in children:
            if child:
                # 자식의 부모는 여전히 현재 노드
                self._update_parent_references(child, node)

    def _adjust_children_order(self, json_node: Dict[str, Any]) -> None:
        """자식 순서 조정 - 원본 Figma 순서 유지"""
        children = json_node.get("children", [])
        if len(children) <= 1:
            return

        # 원본 순서 정보가 있으면 사용, 없으면 기존 로직 사용
        try:
            # 원본 순서 정보 확인
            has_original_order = any(
                child.get("_original_order") is not None for child in children
            )

            if has_original_order:
                # 원본 순서로 정렬
                def sort_key(child: Dict[str, Any]) -> float:
                    return child.get("_original_order", float("inf"))

                children.sort(key=sort_key)
                logging.debug(
                    f"[ORDER DEBUG] Sorted children by original order for '{json_node.get('name', 'unknown')}'"
                )
            else:
                # 기존 로직: Z-인덱스 또는 Y 위치 기반으로 정렬
                def sort_key(child: Dict[str, Any]) -> Tuple[int, int]:
                    # Z-인덱스가 있으면 사용, 없으면 Y 위치 사용
                    z_index = child.get("zIndex", 0)
                    y_pos = child.get("y", 0)
                    return (z_index, y_pos)

                children.sort(key=sort_key)
                logging.debug(
                    f"[ORDER DEBUG] Sorted children by z-index/y-position for '{json_node.get('name', 'unknown')}'"
                )

            json_node["children"] = children
        except (TypeError, KeyError) as e:
            # 정렬 실패 시 원래 순서 유지
            logging.warning(
                f"[ORDER WARNING] Failed to sort children for '{json_node.get('name', 'unknown')}': {e}"
            )
            pass

    def get_performance_stats(self) -> Dict[str, Any]:
        """성능 통계 가져오기"""
        return self.performance_counters.copy()

    def get_css_collection(self) -> Dict[str, Dict[str, Any]]:
        """CSS 컬렉션 가져오기"""
        return self.css_collection.copy()


def convert_nodes_to_json(
    nodes: List[Dict[str, Any]], settings: Optional[Dict[str, Any]] = None
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    노드를 JSON으로 변환하는 편의 함수

    Args:
        nodes: 변환할 노드 리스트
        settings: 변환 설정

    Returns:
        (변환된 노드, 성능 통계)
    """
    converter = JsonNodeConverter()
    return converter.nodes_to_json(nodes, settings)


if __name__ == "__main__":
    # Test the converter
    test_nodes = [
        {
            "id": "1:1",
            "type": "FRAME",
            "name": "Test Frame",
            "absoluteBoundingBox": {"x": 0, "y": 0, "width": 400, "height": 300},
            "layoutMode": "VERTICAL",
            "visible": True,
            "children": [
                {
                    "id": "1:2",
                    "type": "TEXT",
                    "name": "Title",
                    "characters": "Hello World",
                    "absoluteBoundingBox": {
                        "x": 20,
                        "y": 20,
                        "width": 360,
                        "height": 40,
                    },
                    "visible": True,
                    "style": {"fontFamily": "Arial", "fontSize": 24, "fontWeight": 700},
                },
                {
                    "id": "1:3",
                    "type": "GROUP",
                    "name": "Button Group",
                    "absoluteBoundingBox": {
                        "x": 20,
                        "y": 80,
                        "width": 120,
                        "height": 40,
                    },
                    "visible": True,
                    "children": [
                        {
                            "id": "1:4",
                            "type": "RECTANGLE",
                            "name": "Button",
                            "absoluteBoundingBox": {
                                "x": 20,
                                "y": 80,
                                "width": 120,
                                "height": 40,
                            },
                            "visible": True,
                            "fills": [
                                {
                                    "type": "SOLID",
                                    "color": {"r": 0.2, "g": 0.6, "b": 1.0},
                                }
                            ],
                        }
                    ],
                },
            ],
        }
    ]

    converted, stats = convert_nodes_to_json(test_nodes)
    logging.debug("Conversion completed!")
    logging.debug(f"Performance stats: {stats}")
    logging.debug(f"Converted nodes: {len(converted)}")

    # Print first converted node structure
    if converted:
        logging.debug("First converted node:")
        logging.debug(json.dumps(converted[0], indent=2))
