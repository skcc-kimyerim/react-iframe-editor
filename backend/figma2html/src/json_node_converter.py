"""
JSON Node Converter
Figma 노드를 JSON 형식으로 변환하는 고급 컨버터
"""

import math
import json
import logging
from typing import Dict, Any, List, Optional, Tuple, Union
from .style_builder import CSSStyleBuilder, build_css_for_node
from .icon_detection import is_likely_icon
from .utils import generate_unique_class_name


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

    def reset_counters(self):
        """새로운 변환을 위한 카운터 초기화"""
        self.node_name_counters.clear()
        self.css_collection.clear()
        self.performance_counters = {
            "nodes_processed": 0,
            "nodes_skipped": 0,
            "groups_inlined": 0,
        }

    def nodes_to_json(self, nodes: List[Dict[str, Any]], settings: Optional[Dict[str, Any]] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
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
                parent_cumulative_rotation=0
            )
            
            if processed_node is not None:
                if isinstance(processed_node, list):
                    # 인라인된 그룹의 경우 배열 반환 시 모든 노드 추가
                    result.extend(processed_node)
                else:
                    # 단일 노드 반환 시 직접 추가
                    result.append(processed_node)

        logging.debug(f"[JsonNodeConverter] 처리된 노드: {self.performance_counters['nodes_processed']}개, "
              f"건너뛴 노드: {self.performance_counters['nodes_skipped']}개, "
              f"인라인된 그룹: {self.performance_counters['groups_inlined']}개")

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

        # 고유 이름 보장
        self._ensure_unique_name(json_node)

        # 텍스트 노드 처리
        if node_type == "TEXT":
            self._process_text_node(json_node, settings)

        # 크기 및 위치 처리
        self._process_size_and_position(json_node, parent_node)

        # 레이아웃 정보 처리
        self._process_layout_info(json_node)

        # 자식 노드 처리
        children = json_node.get("children", [])
        if children:
            processed_children = []
            
            for child in children:
                # 현재 노드의 회전을 누적 회전에 추가
                current_rotation = json_node.get("rotation", 0)
                if current_rotation:
                    current_rotation = current_rotation * (180 / math.pi)  # 라디안에서 도로 변환
                
                cumulative_rotation = parent_cumulative_rotation + current_rotation

                processed_child = self._process_node_pair(
                    child, settings, json_node, cumulative_rotation
                )
                
                if processed_child is not None:
                    if isinstance(processed_child, list):
                        # 인라인된 그룹의 자식들
                        processed_children.extend(processed_child)
                    else:
                        processed_children.append(processed_child)

            json_node["children"] = processed_children
            
            # 자식 순서 조정 (깊이 기반)
            self._adjust_children_order(json_node)

        # 그룹 인라인 처리
        if (node_type == "FRAME" and 
            json_node.get("name", "").strip() == "" and 
            len(json_node.get("children", [])) > 0):
            
            # 빈 이름의 프레임을 그룹으로 인라인
            self.performance_counters["groups_inlined"] += 1
            return json_node.get("children", [])

        self.performance_counters["nodes_processed"] += 1
        return json_node

    def _ensure_unique_name(self, json_node: Dict[str, Any]):
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

    def _process_text_node(self, json_node: Dict[str, Any], settings: Dict[str, Any]):
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

    def _process_size_and_position(self, json_node: Dict[str, Any], parent_node: Optional[Dict[str, Any]]):
        """크기 및 위치 처리"""
        # 절대 경계 상자에서 크기 정보 추출
        if "absoluteBoundingBox" in json_node:
            bbox = json_node["absoluteBoundingBox"]
            if bbox is None:
                logging.warning(f"[경고] absoluteBoundingBox가 None입니다. node: {json_node.get('name', json_node.get('id', 'unknown'))}")
                bbox = {}
            # 크기 설정
            if "width" not in json_node:
                json_node["width"] = bbox.get("width", 0)
            if "height" not in json_node:
                json_node["height"] = bbox.get("height", 0)

            # 위치 설정 (부모 상대적)
            if parent_node and "absoluteBoundingBox" in parent_node:
                parent_bbox = parent_node["absoluteBoundingBox"]
                if parent_bbox is None:
                    logging.warning(f"[경고] parent absoluteBoundingBox가 None입니다. parent: {parent_node.get('name', parent_node.get('id', 'unknown'))}")
                    parent_bbox = {}
                json_node["x"] = bbox.get("x", 0) - parent_bbox.get("x", 0)
                json_node["y"] = bbox.get("y", 0) - parent_bbox.get("y", 0)
            else:
                json_node["x"] = bbox.get("x", 0)
                json_node["y"] = bbox.get("y", 0)

        # 회전 처리
        if "rotation" in json_node and json_node["rotation"]:
            # 회전된 노드의 경계 상자 재계산
            rotation_degrees = json_node["rotation"] * (180 / math.pi)
            # 원래 크기 저장
            original_width = json_node.get("width", 0)
            original_height = json_node.get("height", 0)
            # 회전을 고려한 새 경계 상자 계산
            if "absoluteBoundingBox" in json_node:
                bbox = json_node["absoluteBoundingBox"]
                if bbox is None:
                    bbox = {}
                new_rect = self._calculate_rectangle_from_bounding_box(bbox, rotation_degrees)
                # 새 크기 및 위치 설정
                json_node.update(new_rect)

    def _calculate_rectangle_from_bounding_box(self, bounding_box: Dict[str, float], rotation_degrees: float) -> Dict[str, float]:
        """회전된 경계 상자에서 사각형 계산"""
        # 단순화된 계산 - 실제로는 더 복잡한 수학이 필요
        width = bounding_box.get("width", 0)
        height = bounding_box.get("height", 0)
        x = bounding_box.get("x", 0)
        y = bounding_box.get("y", 0)

        # 회전 각도에 따른 조정 (단순화됨)
        if abs(rotation_degrees) > 0:
            # 회전된 요소의 경우 경계 상자 크기 조정
            rad = math.radians(abs(rotation_degrees))
            new_width = abs(width * math.cos(rad)) + abs(height * math.sin(rad))
            new_height = abs(width * math.sin(rad)) + abs(height * math.cos(rad))
            
            return {
                "width": new_width,
                "height": new_height,
                "x": x,
                "y": y
            }

        return {
            "width": width,
            "height": height,
            "x": x,
            "y": y
        }

    def _is_likely_icon(self, json_node: Dict[str, Any]) -> bool:
        """노드가 아이콘일 가능성 확인"""
        return is_likely_icon(json_node)

    def _process_layout_info(self, json_node: Dict[str, Any]):
        """레이아웃 정보 처리"""
        # 자동 레이아웃 정보가 있는지 확인
        if "layoutMode" in json_node and json_node["layoutMode"] != "NONE":
            # 자동 레이아웃 노드
            json_node["isAutoLayout"] = True
        else:
            # 수동 레이아웃 노드
            json_node["isAutoLayout"] = False

        # 위치 지정 방식 설정
        json_node["isRelative"] = json_node.get("layoutMode") == "NONE"

    def _adjust_children_order(self, json_node: Dict[str, Any]):
        """자식 순서 조정 (깊이 기반)"""
        children = json_node.get("children", [])
        if len(children) <= 1:
            return

        # Z-인덱스 또는 Y 위치 기반으로 정렬
        try:
            def sort_key(child):
                # Z-인덱스가 있으면 사용, 없으면 Y 위치 사용
                z_index = child.get("zIndex", 0)
                y_pos = child.get("y", 0)
                return (z_index, y_pos)

            children.sort(key=sort_key)
            json_node["children"] = children
        except (TypeError, KeyError):
            # 정렬 실패 시 원래 순서 유지
            pass

    def get_performance_stats(self) -> Dict[str, Any]:
        """성능 통계 가져오기"""
        return self.performance_counters.copy()

    def get_css_collection(self) -> Dict[str, Dict[str, Any]]:
        """CSS 컬렉션 가져오기"""
        return self.css_collection.copy()


def convert_nodes_to_json(nodes: List[Dict[str, Any]], settings: Optional[Dict[str, Any]] = None) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
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
                    "absoluteBoundingBox": {"x": 20, "y": 20, "width": 360, "height": 40},
                    "visible": True,
                    "style": {
                        "fontFamily": "Arial",
                        "fontSize": 24,
                        "fontWeight": 700
                    }
                },
                {
                    "id": "1:3", 
                    "type": "GROUP",
                    "name": "Button Group",
                    "absoluteBoundingBox": {"x": 20, "y": 80, "width": 120, "height": 40},
                    "visible": True,
                    "children": [
                        {
                            "id": "1:4",
                            "type": "RECTANGLE",
                            "name": "Button",
                            "absoluteBoundingBox": {"x": 20, "y": 80, "width": 120, "height": 40},
                            "visible": True,
                            "fills": [{
                                "type": "SOLID",
                                "color": {"r": 0.2, "g": 0.6, "b": 1.0}
                            }]
                        }
                    ]
                }
            ]
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