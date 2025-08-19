"""
SVG Renderer Module
Handles SVG rendering and color variable processing
Ported from FigmaToCode altNodeUtils.ts
"""

import logging
import re
from typing import Any, Dict, List, Optional

import requests

from .figma_api_client import FigmaApiClient


class SVGRenderer:
    """SVG rendering and processing logic ported from FigmaToCode"""

    def __init__(self, api_client: FigmaApiClient):
        self.api_client = api_client
        self.warnings: List[str] = []

    def render_and_attach_svg(self, node: Dict[str, Any]) -> Dict[str, Any]:
        """
        Renders a node as SVG and attaches it to the node data

        Args:
            node: The node to render as SVG

        Returns:
            The node with SVG data attached
        """
        if not node.get("canBeFlattened", False):
            return node

        if node.get("svg"):
            return node

        try:
            # Export node as SVG using Figma API
            svg_content = self._export_node_as_svg(node)

            if not svg_content:
                self._add_warning(
                    f"Failed to export SVG for {node.get('name', 'unnamed')}"
                )
                return node

            # Process the SVG to replace colors with variable references
            color_mappings = node.get("colorVariableMappings", {})
            if color_mappings:
                processed_svg = self._process_svg_colors(svg_content, color_mappings)
                node["svg"] = processed_svg
            else:
                node["svg"] = svg_content

        except Exception as error:
            self._add_warning(f"Failed rendering SVG for {node.get('name', 'unnamed')}")
            logging.error(
                f"Error rendering SVG for {node.get('type', 'unknown')}:{node.get('id', 'no-id')}"
            )
            logging.error(f"Error: {str(error)}")

        return node

    def render_shape_as_svg(
        self, node: Dict[str, Any], file_key: str
    ) -> Dict[str, Any]:
        """
        polygon과 ellipse 타입을 SVG로 렌더링하고 노드에 첨부

        Args:
            node: 렌더링할 노드
            file_key: Figma 파일 키

        Returns:
            SVG가 첨부된 노드
        """
        node_type = node.get("type")
        node_id = node.get("id")

        # polygon과 ellipse 타입만 처리
        if node_type not in ["ELLIPSE", "REGULAR_POLYGON"]:
            return node

        # 이미 SVG가 있으면 그대로 반환
        if node.get("svg"):
            return node

        try:
            # API 클라이언트를 통해 SVG 렌더링
            svg_content = self.api_client.get_shape_as_svg(file_key, node_id, node)

            if svg_content:
                # SVG를 노드에 첨부
                node["svg"] = svg_content
                node["canBeFlattened"] = True
                logging.info(
                    f"Shape SVG 렌더링 성공: {node.get('name', 'unnamed')} ({node_type})"
                )
            else:
                self._add_warning(
                    f"Shape SVG 렌더링 실패: {node.get('name', 'unnamed')} ({node_type})"
                )

        except Exception as error:
            self._add_warning(
                f"Shape SVG 처리 중 오류: {node.get('name', 'unnamed')} ({node_type})"
            )
            logging.error(f"Error rendering shape SVG for {node_type}:{node_id}")
            logging.error(f"Error: {str(error)}")

        return node

    def process_shapes_in_nodes(
        self, nodes: List[Dict[str, Any]], file_key: str
    ) -> List[Dict[str, Any]]:
        """
        노드 리스트에서 polygon과 ellipse 타입을 찾아 SVG로 렌더링 - 원본 순서 유지

        Args:
            nodes: 처리할 노드 리스트
            file_key: Figma 파일 키

        Returns:
            SVG가 첨부된 노드 리스트
        """
        processed_nodes = []

        # 원본 순서 정보가 있으면 정렬
        has_original_order = any(
            node.get("_original_order") is not None for node in nodes
        )
        if has_original_order:
            nodes = sorted(
                nodes, key=lambda node: node.get("_original_order", float("inf"))
            )
            logging.debug(
                f"[SVG ORDER] Sorted nodes by original order for SVG processing"
            )

        for node in nodes:
            # 현재 노드 처리
            processed_node = self.render_shape_as_svg(node, file_key)
            processed_nodes.append(processed_node)

            # 자식 노드들도 재귀적으로 처리
            if "children" in processed_node and isinstance(
                processed_node["children"], list
            ):
                processed_node["children"] = self.process_shapes_in_nodes(
                    processed_node["children"], file_key
                )

        return processed_nodes

    def _export_node_as_svg(self, node: Dict[str, Any]) -> Optional[str]:
        """
        Export a node as SVG using Figma API
        Args:
            node: The node to export
        Returns:
            SVG string or None if failed
        """
        try:
            file_key = node.get("file_key")
            node_id = node.get("node_id")
            if file_key and node_id:
                images = self.api_client.get_images(file_key, [node_id], format="svg")
                if images and node_id in images and images[node_id]:
                    svg_url = images[node_id]
                    resp = requests.get(svg_url)
                    if resp.status_code == 200:
                        svg_content = resp.text
                        # SVG를 노드 크기에 맞게 조정
                        return self._adjust_svg_size(svg_content, node)
                    else:
                        self._add_warning(f"Failed to download SVG for node {node_id}")

            # fallback: placeholder SVG
            width = node.get("width", 24)
            height = node.get("height", 24)
            name = node.get("name", "icon")
            placeholder_svg = f'''<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect width="{width}" height="{height}" fill="#F3F4F6"/>
<path d="M8 8L16 16M16 8L8 16" stroke="#9CA3AF" stroke-width="2" stroke-linecap="round"/>
</svg>'''
            return placeholder_svg
        except Exception as e:
            logging.error(f"Error exporting SVG: {str(e)}")
            width = node.get("width", 24)
            height = node.get("height", 24)
            placeholder_svg = f'''<svg width="{width}" height="{height}" viewBox="0 0 {width} {height}" fill="none" xmlns="http://www.w3.org/2000/svg">
<rect width="{width}" height="{height}" fill="#F3F4F6"/>
<path d="M8 8L16 16M16 8L8 16" stroke="#9CA3AF" stroke-width="2" stroke-linecap="round"/>
</svg>'''
            return placeholder_svg

    def _adjust_svg_size(self, svg_content: str, node: Dict[str, Any]) -> str:
        """
        SVG 콘텐츠를 노드 크기에 맞게 조정

        Args:
            svg_content: 원본 SVG 문자열
            node: 노드 정보

        Returns:
            조정된 SVG 문자열
        """
        import re

        target_width = node.get("width", 24)
        target_height = node.get("height", 24)

        # SVG 태그에서 기존 width, height, viewBox 추출
        svg_tag_pattern = r"<svg([^>]*)>"
        svg_match = re.search(svg_tag_pattern, svg_content)

        if not svg_match:
            return svg_content

        svg_attrs = svg_match.group(1)

        # 기존 속성들 추출
        width_match = re.search(r'width=["\']([^"\']*)["\']', svg_attrs)
        height_match = re.search(r'height=["\']([^"\']*)["\']', svg_attrs)
        viewbox_match = re.search(r'viewBox=["\']([^"\']*)["\']', svg_attrs)

        # 기존 크기 파싱 (단위 제거)
        def parse_size(size_str: str) -> float:
            if not size_str:
                return target_width
            # 단위 제거 (px, pt 등)
            size_str = re.sub(r"[^\d.]", "", size_str)
            return float(size_str) if size_str else target_width

        original_width = parse_size(width_match.group(1) if width_match else None)
        original_height = parse_size(height_match.group(1) if height_match else None)

        # viewBox 파싱
        if viewbox_match:
            viewbox_parts = viewbox_match.group(1).split()
            if len(viewbox_parts) >= 4:
                vb_x = float(viewbox_parts[0])
                vb_y = float(viewbox_parts[1])
                vb_width = float(viewbox_parts[2])
                vb_height = float(viewbox_parts[3])
            else:
                vb_x, vb_y, vb_width, vb_height = 0, 0, original_width, original_height
        else:
            vb_x, vb_y, vb_width, vb_height = 0, 0, original_width, original_height

        # 새로운 viewBox 계산 (비율 유지)
        scale_x = target_width / vb_width if vb_width > 0 else 1
        scale_y = target_height / vb_height if vb_height > 0 else 1
        scale = min(scale_x, scale_y)  # 비율 유지

        new_vb_width = vb_width * scale
        new_vb_height = vb_height * scale
        new_vb_x = vb_x + (vb_width - new_vb_width) / 2
        new_vb_y = vb_y + (vb_height - new_vb_height) / 2

        # 새로운 SVG 태그 생성
        new_svg_attrs = svg_attrs

        # width, height 속성 업데이트
        if width_match:
            new_svg_attrs = re.sub(
                r'width=["\']([^"\']*)["\']', f'width="{target_width}"', new_svg_attrs
            )
        else:
            new_svg_attrs += f' width="{target_width}"'

        if height_match:
            new_svg_attrs = re.sub(
                r'height=["\']([^"\']*)["\']',
                f'height="{target_height}"',
                new_svg_attrs,
            )
        else:
            new_svg_attrs += f' height="{target_height}"'

        # viewBox 속성 업데이트
        new_viewbox = f"{new_vb_x} {new_vb_y} {new_vb_width} {new_vb_height}"
        if viewbox_match:
            new_svg_attrs = re.sub(
                r'viewBox=["\']([^"\']*)["\']',
                f'viewBox="{new_viewbox}"',
                new_svg_attrs,
            )
        else:
            new_svg_attrs += f' viewBox="{new_viewbox}"'

        # xmlns 속성 추가 (없는 경우)
        if "xmlns=" not in new_svg_attrs:
            new_svg_attrs += ' xmlns="http://www.w3.org/2000/svg"'

        # 새로운 SVG 태그로 교체
        new_svg_tag = f"<svg{new_svg_attrs}>"
        adjusted_svg = re.sub(svg_tag_pattern, new_svg_tag, svg_content)

        return adjusted_svg

    def _process_svg_colors(
        self, svg_content: str, color_mappings: Dict[str, Dict[str, str]]
    ) -> str:
        """
        Process SVG content to replace colors with CSS variables

        Args:
            svg_content: The original SVG content
            color_mappings: Mapping of colors to variable names

        Returns:
            Processed SVG with color variables
        """
        processed_svg = svg_content

        # Replace fill="COLOR" or stroke="COLOR" patterns
        color_attribute_regex = r'(fill|stroke)="([^"]*)"'

        def replace_color_attribute(match: re.Match[str]) -> str:
            attribute = match.group(1)
            color_value = match.group(2)

            # Clean up the color value and normalize it
            normalized_color = color_value.lower().strip()

            # Look up the color directly in our mappings
            mapping = color_mappings.get(normalized_color)
            if mapping:
                variable_name = mapping.get("variableName")
                if variable_name:
                    # If we have a variable reference, use it with fallback to original
                    return f'{attribute}="var(--{variable_name}, {color_value})"'

            # Otherwise keep the original color
            return match.group(0)

        processed_svg = re.sub(
            color_attribute_regex, replace_color_attribute, processed_svg
        )

        # Also handle style attributes with fill: or stroke: properties
        style_regex = r'style="([^"]*)(?:(fill|stroke):\s*([^;"]*))([;"]*)([^"]*)"'

        def replace_style_attribute(match: re.Match[str]) -> str:
            prefix = match.group(1)
            property_name = match.group(2)
            color_value = match.group(3)
            separator = match.group(4)
            suffix = match.group(5)

            # Clean up any extra spaces from the color value
            normalized_color = color_value.lower().strip()

            # Look up the color directly in our mappings
            mapping = color_mappings.get(normalized_color)
            if mapping:
                variable_name = mapping.get("variableName")
                if variable_name:
                    # Replace just the color value with the variable and fallback
                    return f'style="{prefix}{property_name}: var(--{variable_name}, {color_value}){separator}{suffix}"'

            return match.group(0)

        processed_svg = re.sub(style_regex, replace_style_attribute, processed_svg)

        return processed_svg

    def is_svg_node(self, node: Dict[str, Any]) -> bool:
        """Check if a node can be flattened to SVG"""
        return node.get("canBeFlattened", False)

    def is_shape_node(self, node: Dict[str, Any]) -> bool:
        """Check if a node is a shape that should be rendered as SVG"""
        node_type = node.get("type")
        return node_type in ["ELLIPSE", "REGULAR_POLYGON"]

    def _add_warning(self, message: str) -> None:
        """Add a warning message"""
        if message not in self.warnings:
            self.warnings.append(message)

    def get_warnings(self) -> List[str]:
        """Get all warning messages"""
        return self.warnings.copy()

    def clear_warnings(self) -> None:
        """Clear all warning messages"""
        self.warnings.clear()


def create_svg_renderer(api_client: FigmaApiClient) -> SVGRenderer:
    """Factory function to create SVG renderer"""
    return SVGRenderer(api_client)
