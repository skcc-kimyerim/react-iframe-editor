"""
HTML Generator
Figma 노드를 HTML/CSS로 변환하는 고급 생성기
"""

import logging
from typing import Any, Dict, List, Optional

from .batch_processor import BatchProcessor, ProcessedResult
from .figma_api_client import FigmaApiClient
from .image_processor import ImageProcessor
from .style_builder import CSSStyleBuilder
from .svg_renderer import SVGRenderer
from .utils import generate_unique_class_name, indent_string


class HtmlGenerator:
    """Figma 노드를 HTML/CSS로 변환하는 고급 생성기"""

    def __init__(
        self,
        settings: Optional[Dict[str, Any]] = None,
        api_client: Optional[FigmaApiClient] = None,
    ):
        self.settings = settings or {}
        self.css_collection: Dict[str, str] = {}
        self.class_name_counters: Dict[str, int] = {}
        self.warnings: List[str] = []
        self.is_preview = False
        self.processed_results: Dict[str, ProcessedResult] = {}

        # SVG 및 이미지 프로세서 초기화
        if api_client:
            self.svg_renderer = SVGRenderer(api_client)
            self.image_processor = ImageProcessor(api_client)
            self.batch_processor = BatchProcessor(api_client)
        else:
            self.svg_renderer = None
            self.image_processor = None
            self.batch_processor = None

    def reset_state(self) -> None:
        """새로운 변환을 위한 상태 초기화"""
        self.css_collection.clear()
        self.class_name_counters.clear()
        self.warnings.clear()
        self.processed_results.clear()

    def html_main(
        self, scene_nodes: List[Dict[str, Any]], is_preview: bool = False
    ) -> Dict[str, str]:
        """
        메인 HTML 생성 함수

        Args:
            scene_nodes: 처리된 scene 노드 리스트
            is_preview: 미리보기 모드 여부

        Returns:
            'html'과 'css' 키를 가진 딕셔너리
        """
        self.is_preview = is_preview
        self.reset_state()

        # 배치 프로세서를 사용하여 SVG/이미지 처리
        if self.batch_processor and not is_preview:
            # 설정에 따라 배치 처리 실행
            if self.settings.get("embedVectors") or self.settings.get("embedImages"):
                self.processed_results = self.batch_processor.process_nodes_batch(
                    scene_nodes, self.settings
                )
                # 배치 프로세서의 경고 합치기
                self.warnings.extend(self.batch_processor.get_warnings())

        html_content = self._html_widget_generator(scene_nodes, is_root=True)

        # 초기 줄바꿈 제거
        if html_content.startswith("\n"):
            html_content = html_content[1:]

        # CSS 생성
        css_content = self._get_collected_css()

        return {"html": html_content, "css": css_content}

    def _html_widget_generator(
        self,
        scene_nodes: List[Dict[str, Any]],
        is_root: bool = False,
        parent_node: Optional[Dict[str, Any]] = None,
    ) -> str:
        """여러 노드에 대한 HTML 생성 - 원본 순서 유지"""
        # 보이는 노드만 필터링
        visible_nodes = [node for node in scene_nodes if node.get("visible", True)]

        # 원본 순서 정보가 있으면 정렬, 없으면 기존 순서 유지
        has_original_order = any(
            node.get("_original_order") is not None for node in visible_nodes
        )

        if has_original_order:
            # 원본 순서로 정렬
            visible_nodes.sort(
                key=lambda node: node.get("_original_order", float("inf"))
            )
            logging.debug(
                f"[HTML ORDER] Sorted nodes by original order for parent '{parent_node.get('name', 'root') if parent_node else 'root'}'"
            )
        else:
            # 기존 순서 유지 (Z-인덱스 기반 정렬)
            try:
                visible_nodes.sort(
                    key=lambda node: (node.get("zIndex", 0), node.get("y", 0))
                )
                logging.debug(
                    f"[HTML ORDER] Sorted nodes by z-index for parent '{parent_node.get('name', 'root') if parent_node else 'root'}'"
                )
            except (TypeError, KeyError):
                # 정렬 실패 시 원래 순서 유지
                logging.debug(
                    f"[HTML ORDER] Using original order for parent '{parent_node.get('name', 'root') if parent_node else 'root'}'"
                )

        # 각 노드 변환
        html_parts = []
        for node in visible_nodes:
            html = self._convert_node(node, is_root, parent_node)
            if html:
                html_parts.append(html)

        return "".join(html_parts)

    def _convert_node(
        self,
        node: Dict[str, Any],
        is_root: bool = False,
        parent_node: Optional[Dict[str, Any]] = None,
    ) -> str:
        """단일 노드를 HTML로 변환"""
        node_type = node.get("type")
        node_id = node.get("node_id")

        # polygon과 ellipse 타입을 SVG로 처리
        if node_type in ["ELLIPSE", "REGULAR_POLYGON"]:
            # SVG 렌더러가 있고 embedShapes 설정이 활성화되어 있으면 SVG로 렌더링
            if (
                self.svg_renderer
                and not self.is_preview
                and self.settings.get("embedShapes", True)
            ):
                file_key = node.get("file_key")
                if file_key:
                    # SVG로 렌더링
                    processed_node = self.svg_renderer.render_shape_as_svg(
                        node, file_key
                    )
                    if processed_node.get("svg"):
                        return self._html_wrap_svg(processed_node, is_root, parent_node)
                    else:
                        self._add_warning(
                            f"SVG 렌더링 실패: {node.get('name', 'unnamed')} ({node_type})"
                        )

            # SVG 렌더링이 실패하거나 미리보기 모드면 기본 컨테이너로 처리
            return self._html_container(node, "", [], is_root, parent_node)

        # 배치 처리된 결과에서 SVG 콘텐츠 확인
        if (
            self.settings.get("embedVectors")
            and node.get("canBeFlattened")
            and node_id in self.processed_results
        ):
            result = self.processed_results[node_id]
            if result.success and result.content:
                # SVG 콘텐츠를 노드에 첨부
                updated_node = {**node, "svg": result.content}
                return self._html_wrap_svg(updated_node, is_root, parent_node)

        # 노드 타입에 따른 라우팅
        if node_type in ["RECTANGLE"]:
            return self._html_container(node, "", [], is_root, parent_node)
        elif node_type == "GROUP":
            return self._html_group(node, is_root, parent_node)
        elif node_type in ["FRAME", "COMPONENT", "INSTANCE", "COMPONENT_SET"]:
            return self._html_frame(node, is_root, parent_node)
        elif node_type == "SECTION":
            return self._html_section(node, is_root, parent_node)
        elif node_type == "TEXT":
            return self._html_text(node, is_root, parent_node)
        elif node_type == "LINE":
            return self._html_line(node, is_root, parent_node)
        elif node_type == "VECTOR":
            if not self.settings.get("embedVectors") and not self.is_preview:
                self._add_warning("Vector는 지원되지 않습니다")
            # 사각형으로 처리
            return self._html_container(
                {**node, "type": "RECTANGLE"}, "", [], is_root, parent_node
            )
        else:
            self._add_warning(f"{node_type} 노드는 지원되지 않습니다")
            return ""

    def _html_group(
        self,
        node: Dict[str, Any],
        is_root: bool = False,
        parent_node: Optional[Dict[str, Any]] = None,
    ) -> str:
        """GROUP 노드를 HTML로 변환"""
        # 크기가 0이거나 자식이 없으면 무시
        width = node.get("width", 0)
        height = node.get("height", 0)
        children = node.get("children", [])

        if width <= 0 or height <= 0 or not children:
            return ""

        # 그룹에 대한 스타일 생성
        builder = self._create_html_builder(node)
        if not is_root:
            builder.add_position_styles(node, parent_node)

        # 자식 HTML 생성
        children_html = self._html_widget_generator(children, False, node)

        if builder.styles:
            class_name = generate_unique_class_name(node, self.class_name_counters)
            css_styles = builder.build()
            self.css_collection[class_name] = css_styles
            return f'\n<div class="{class_name}">{indent_string(children_html)}\n</div>'
        else:
            return children_html

    def _html_frame(
        self,
        node: Dict[str, Any],
        is_root: bool = False,
        parent_node: Optional[Dict[str, Any]] = None,
    ) -> str:
        """FRAME 노드를 HTML로 변환"""
        children = node.get("children", [])
        children_html = self._html_widget_generator(children, False, node)

        layout_mode = node.get("layoutMode", "NONE")
        if layout_mode != "NONE":
            # 자동 레이아웃 프레임
            additional_styles = self._html_auto_layout_props(node)
            return self._html_container(
                node, children_html, additional_styles, is_root, parent_node
            )
        else:
            # 수동 레이아웃 프레임 - 자식들이 절대 위치 지정됨
            return self._html_container(node, children_html, [], is_root, parent_node)

    def _html_text(
        self,
        node: Dict[str, Any],
        is_root: bool = False,
        parent_node: Optional[Dict[str, Any]] = None,
    ) -> str:
        """TEXT 노드를 HTML로 변환"""
        # 레이아웃 스타일 빌드
        builder = self._create_html_builder(node)
        if not is_root:
            builder.add_position_styles(node, parent_node)
        builder.add_text_styles(node)

        # 텍스트 세그먼트 가져오기
        styled_segments = self._get_text_segments(node)

        if len(styled_segments) == 1:
            # 단일 세그먼트
            segment = styled_segments[0]
            class_name = generate_unique_class_name(node, self.class_name_counters)

            # 빌더 스타일과 세그먼트 스타일 결합
            builder.add_styles_from_dict(segment.get("styles", {}))
            css_styles = builder.build()

            self.css_collection[class_name] = css_styles

            text_content = segment["text"]

            # 아래첨자/위첨자 처리
            if segment.get("openTypeFeatures", {}).get("SUBS"):
                text_content = f"<sub>{text_content}</sub>"
            elif segment.get("openTypeFeatures", {}).get("SUPS"):
                text_content = f"<sup>{text_content}</sup>"

            return f'\n<div class="{class_name}">{text_content}</div>'
        else:
            # 다중 세그먼트
            class_name = generate_unique_class_name(node, self.class_name_counters)
            css_styles = builder.build()
            self.css_collection[class_name] = css_styles

            content_parts = []
            for segment in styled_segments:
                text = segment["text"]
                segment_styles = segment.get("styles", {})

                # 세그먼트에 대한 인라인 스타일 생성
                style_str = "; ".join([f"{k}: {v}" for k, v in segment_styles.items()])

                tag = "span"
                if segment.get("openTypeFeatures", {}).get("SUBS"):
                    tag = "sub"
                elif segment.get("openTypeFeatures", {}).get("SUPS"):
                    tag = "sup"

                if style_str:
                    content_parts.append(f'<{tag} style="{style_str}">{text}</{tag}>')
                else:
                    content_parts.append(f"<{tag}>{text}</{tag}>")

            content = "".join(content_parts)
            return f'\n<div class="{class_name}">{content}</div>'

    def _html_container(
        self,
        node: Dict[str, Any],
        children: str,
        additional_styles: List[str],
        is_root: bool = False,
        parent_node: Optional[Dict[str, Any]] = None,
    ) -> str:
        """HTML 컨테이너 생성"""
        # 크기가 0인 컨테이너 무시
        width = node.get("width", 0)
        height = node.get("height", 0)
        if width <= 0 or height <= 0:
            return children

        builder = self._create_html_builder(node)
        if not is_root:
            node_name = node.get("name", "unknown")
            parent_name = parent_node.get("name", "unknown") if parent_node else "None"
            parent_layout = (
                parent_node.get("layoutMode", "unknown") if parent_node else "None"
            )
            logging.debug(
                f"[HTML CONTAINER DEBUG] Node: '{node_name}' | Parent: '{parent_name}' | Parent Layout: '{parent_layout}'"
            )
            builder.add_position_styles(node, parent_node)
        else:
            # 루트 노드인 경우 전체 화면 스타일 적용
            builder.add_style("position", "fixed")
            builder.add_style("top", "0")
            builder.add_style("left", "0")
            builder.add_style("width", "100vw")
            builder.add_style("height", "100vh")
            builder.add_style("overflow-y", "auto")
            builder.add_style("overflow-x", "hidden")
            builder.add_style("box-sizing", "border-box")
            builder.add_style("margin", "0")
            builder.add_style("padding", "0")

        builder.add_background_styles(node)
        builder.add_border_styles(node)

        # 추가 스타일 적용
        for style in additional_styles:
            if ":" in style:
                prop, value = style.split(":", 1)
                builder.add_style(prop.strip(), value.strip())

        class_name = generate_unique_class_name(node, self.class_name_counters)
        css_styles = builder.build()

        if css_styles:
            self.css_collection[class_name] = css_styles

        # 루트 노드인 경우 root-container 클래스 추가
        if is_root:
            class_name = f"root-container {class_name}"

        # HTML 태그 결정
        tag = "div"
        src = ""

        # 배치 처리된 결과에서 이미지 확인
        if self._node_has_image_fill(node):
            node_id = node.get("node_id")
            if node_id in self.processed_results:
                result = self.processed_results[node_id]
                if result.success and result.content:
                    # 배치 처리로 가져온 이미지 사용
                    if children:
                        # 배경 이미지로 사용 - CSS에는 추가하지 않음 (HTML에 이미 포함됨)
                        pass
                    else:
                        # img 태그로 사용
                        tag = "img"
                        src = f' src="{result.content}"'
                else:
                    # 실패한 경우 플레이스홀더 사용
                    if not children:
                        tag = "img"
                        src = ' src="https://via.placeholder.com/150"'
                    else:
                        # 배경 이미지로 사용 - CSS에는 추가하지 않음
                        pass
            else:
                # 배치 처리되지 않은 경우 플레이스홀더 사용
                if not children:
                    tag = "img"
                    src = ' src="https://via.placeholder.com/150"'
                else:
                    # 배경 이미지로 사용 - CSS에는 추가하지 않음
                    pass

        if children:
            return f'\n<{tag} class="{class_name}"{src}>{indent_string(children)}\n</{tag}>'
        else:
            return f'\n<{tag} class="{class_name}"{src}></{tag}>'

    def _html_section(
        self,
        node: Dict[str, Any],
        is_root: bool = False,
        parent_node: Optional[Dict[str, Any]] = None,
    ) -> str:
        """SECTION 노드를 HTML로 변환"""
        children = node.get("children", [])
        children_html = self._html_widget_generator(children, False, node)

        builder = self._create_html_builder(node)
        builder.add_size_styles(node)
        if not is_root:
            builder.add_position_styles(node, parent_node)
        builder.add_background_styles(node)

        class_name = generate_unique_class_name(node, self.class_name_counters)
        css_styles = builder.build()
        self.css_collection[class_name] = css_styles

        if children_html:
            return f'\n<div class="{class_name}">{indent_string(children_html)}\n</div>'
        else:
            return f'\n<div class="{class_name}"></div>'

    def _html_line(
        self,
        node: Dict[str, Any],
        is_root: bool = False,
        parent_node: Optional[Dict[str, Any]] = None,
    ) -> str:
        """LINE 노드를 HTML로 변환"""
        builder = self._create_html_builder(node)
        if not is_root:
            builder.add_position_styles(node, parent_node)
        builder.add_border_styles(node)

        class_name = generate_unique_class_name(node, self.class_name_counters)
        css_styles = builder.build()
        self.css_collection[class_name] = css_styles

        return f'\n<div class="{class_name}"></div>'

    def _html_wrap_svg(
        self,
        node: Dict[str, Any],
        is_root: bool = False,
        parent_node: Optional[Dict[str, Any]] = None,
    ) -> str:
        """SVG 콘텐츠 래핑"""
        class_name = generate_unique_class_name(node, self.class_name_counters)
        builder = self._create_html_builder(node)
        if not is_root:
            builder.add_position_styles(node, parent_node)

        # SVG 컨테이너를 위한 추가 스타일
        node_width = node.get("width", 24)
        node_height = node.get("height", 24)
        builder.add_style("width", f"{node_width}px")
        builder.add_style("height", f"{node_height}px")
        builder.add_style("display", "flex")
        builder.add_style("align-items", "center")
        builder.add_style("justify-content", "center")

        css_styles = builder.build()
        self.css_collection[class_name] = css_styles

        svg_content = node.get("svg")
        if not svg_content:
            # 플레이스홀더 SVG
            svg_content = f'''<svg width="{node_width}" height="{node_height}" viewBox="0 0 {node_width} {node_height}" fill="none" xmlns="http://www.w3.org/2000/svg">
                <rect width="{node_width}" height="{node_height}" fill="#ddd"/>
                <text x="{node_width / 2}" y="{node_height / 2}" text-anchor="middle" dy=".3em" font-size="8">SVG</text>
            </svg>'''
        else:
            # 기존 SVG를 노드 크기에 맞게 조정
            svg_content = self._adjust_svg_to_node_size(
                svg_content, node_width, node_height
            )

        return f'\n<div class="{class_name}">{svg_content}</div>'

    def _adjust_svg_to_node_size(
        self, svg_content: str, target_width: float, target_height: float
    ) -> str:
        """
        SVG 콘텐츠를 노드 크기에 맞게 조정

        Args:
            svg_content: 원본 SVG 문자열
            target_width: 목표 너비
            target_height: 목표 높이

        Returns:
            조정된 SVG 문자열
        """
        import re

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

        # 기존 크기 파싱
        original_width = float(width_match.group(1)) if width_match else target_width
        original_height = (
            float(height_match.group(1)) if height_match else target_height
        )

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

    def _html_auto_layout_props(self, node: Dict[str, Any]) -> List[str]:
        """자동 레이아웃 CSS 속성 생성 - 새로운 스타일 빌더 사용"""
        # 새로운 스타일 빌더를 사용하여 auto layout 스타일 생성
        builder = CSSStyleBuilder()
        builder.add_auto_layout_styles(node)
        builder.add_padding(node)

        # 스타일을 문자열 배열로 변환
        styles = []
        style_dict = builder.build_dict()
        for prop, value in style_dict.items():
            styles.append(f"{prop}: {value}")

        return styles

    def _create_html_builder(self, node: Dict[str, Any]) -> CSSStyleBuilder:
        """노드에 대한 CSS 스타일 빌더 생성"""
        return CSSStyleBuilder()

    def _get_text_segments(self, node: Dict[str, Any]) -> List[Dict[str, Any]]:
        """스타일이 적용된 텍스트 세그먼트 가져오기"""
        characters = node.get("characters", "")
        if not characters:
            return []

        # 단일 세그먼트 생성
        style = node.get("style", {})

        # 스타일을 CSS 속성으로 변환
        css_styles = {}
        if "fontFamily" in style:
            css_styles["font-family"] = style["fontFamily"]
        if "fontSize" in style:
            css_styles["font-size"] = f"{style['fontSize']}px"
        if "fontWeight" in style:
            css_styles["font-weight"] = str(style["fontWeight"])

        # 줄바꿈 처리
        text_with_breaks = characters.replace("\n", "<br/>")

        return [
            {"text": text_with_breaks, "styles": css_styles, "openTypeFeatures": {}}
        ]

    def _get_collected_css(self) -> str:
        """수집된 클래스에서 CSS 생성"""
        if not self.css_collection:
            return ""

        css_parts = ["/* Figma에서 생성된 CSS */\n"]

        # 기본 리셋 추가
        css_parts.append("""* {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

html, body {
    height: 100%;
    overflow: hidden;
}

body {
    font-family: system-ui, -apple-system, sans-serif;
    line-height: 1.6;
}

/* 루트 컨테이너 스타일 */
.root-container {
    position: fixed;
    top: 0;
    left: 0;
    width: 100vw;
    height: 100vh;
    overflow-y: auto;
    overflow-x: hidden;
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

/* 반응형 스타일 */
@media (max-width: 768px) {
    .root-container {
        padding: 10px;
    }
}

@media (max-width: 480px) {
    .root-container {
        padding: 5px;
    }
}

/* SVG 컨테이너 스타일 */
svg {
    display: block;
    max-width: 100%;
    max-height: 100%;
    width: auto;
    height: auto;
}

""")

        # 수집된 클래스 추가
        for class_name, styles in self.css_collection.items():
            css_parts.append(f".{class_name} {{\n")
            style_parts = styles.split(";")
            for style in style_parts:
                if style.strip():
                    css_parts.append(f"    {style.strip()};\n")
            css_parts.append("}\n\n")

        return "".join(css_parts)

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


def generate_html_from_nodes(
    nodes: List[Dict[str, Any]], settings: Optional[Dict[str, Any]] = None
) -> Dict[str, str]:
    """
    처리된 노드에서 HTML 생성하는 편의 함수

    Args:
        nodes: 처리된 Figma 노드 리스트
        settings: 생성 설정

    Returns:
        'html'과 'css' 키를 가진 딕셔너리
    """
    generator = HtmlGenerator(settings)
    return generator.html_main(nodes)
