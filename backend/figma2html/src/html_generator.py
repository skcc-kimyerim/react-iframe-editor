"""
HTML Generator
Figma 노드를 HTML/CSS로 변환하는 고급 생성기
"""

from typing import Dict, Any, List, Optional
from .style_builder import CSSStyleBuilder
from .svg_renderer import SVGRenderer
from .image_processor import ImageProcessor
from .utils import generate_unique_class_name, indent_string


class HtmlGenerator:
    """Figma 노드를 HTML/CSS로 변환하는 고급 생성기"""

    def __init__(self, settings: Optional[Dict[str, Any]] = None, api_client=None):
        self.settings = settings or {}
        self.css_collection: Dict[str, str] = {}
        self.class_name_counters: Dict[str, int] = {}
        self.warnings: List[str] = []
        self.is_preview = False
        
        # SVG 및 이미지 프로세서 초기화
        if api_client:
            self.svg_renderer = SVGRenderer(api_client)
            self.image_processor = ImageProcessor(api_client)
        else:
            self.svg_renderer = None
            self.image_processor = None

    def reset_state(self):
        """새로운 변환을 위한 상태 초기화"""
        self.css_collection.clear()
        self.class_name_counters.clear()
        self.warnings.clear()

    def html_main(self, scene_nodes: List[Dict[str, Any]], is_preview: bool = False) -> Dict[str, str]:
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

        html_content = self._html_widget_generator(scene_nodes)

        # 초기 줄바꿈 제거
        if html_content.startswith("\n"):
            html_content = html_content[1:]

        # CSS 생성
        css_content = self._get_collected_css()

        return {
            "html": html_content,
            "css": css_content
        }

    def _html_widget_generator(self, scene_nodes: List[Dict[str, Any]]) -> str:
        """여러 노드에 대한 HTML 생성"""
        # 보이는 노드만 필터링
        visible_nodes = [node for node in scene_nodes if node.get("visible", True)]

        # 각 노드 변환
        html_parts = []
        for node in visible_nodes:
            html = self._convert_node(node)
            if html:
                html_parts.append(html)

        return "".join(html_parts)

    def _convert_node(self, node: Dict[str, Any]) -> str:
        """단일 노드를 HTML로 변환"""
        node_type = node.get("type")

        # 벡터에 대한 SVG 임베딩 처리
        if (self.settings.get("embedVectors") and 
            node.get("canBeFlattened") and 
            self.svg_renderer):
            svg_node = self.svg_renderer.render_and_attach_svg(node)
            if svg_node.get("svg"):
                return self._html_wrap_svg(svg_node)

        # 노드 타입에 따른 라우팅
        if node_type in ["RECTANGLE", "ELLIPSE"]:
            return self._html_container(node, "", [])
        elif node_type == "GROUP":
            return self._html_group(node)
        elif node_type in ["FRAME", "COMPONENT", "INSTANCE", "COMPONENT_SET"]:
            return self._html_frame(node)
        elif node_type == "SECTION":
            return self._html_section(node)
        elif node_type == "TEXT":
            return self._html_text(node)
        elif node_type == "LINE":
            return self._html_line(node)
        elif node_type == "VECTOR":
            if not self.settings.get("embedVectors") and not self.is_preview:
                self._add_warning("Vector는 지원되지 않습니다")
            # 사각형으로 처리
            return self._html_container({**node, "type": "RECTANGLE"}, "", [])
        else:
            self._add_warning(f"{node_type} 노드는 지원되지 않습니다")
            return ""

    def _html_group(self, node: Dict[str, Any]) -> str:
        """GROUP 노드를 HTML로 변환"""
        # 크기가 0이거나 자식이 없으면 무시
        width = node.get("width", 0)
        height = node.get("height", 0)
        children = node.get("children", [])

        if width <= 0 or height <= 0 or not children:
            return ""

        # 그룹에 대한 스타일 생성
        builder = self._create_html_builder(node)
        builder.add_position_styles(node)

        # 자식 HTML 생성
        children_html = self._html_widget_generator(children)

        if builder.styles:
            class_name = generate_unique_class_name(node, self.class_name_counters)
            css_styles = builder.build()
            self.css_collection[class_name] = css_styles
            return f'\n<div class="{class_name}">{indent_string(children_html)}\n</div>'
        else:
            return children_html

    def _html_frame(self, node: Dict[str, Any]) -> str:
        """FRAME 노드를 HTML로 변환"""
        children = node.get("children", [])
        children_html = self._html_widget_generator(children)

        layout_mode = node.get("layoutMode", "NONE")
        if layout_mode != "NONE":
            # 자동 레이아웃 프레임
            additional_styles = self._html_auto_layout_props(node)
            return self._html_container(node, children_html, additional_styles)
        else:
            # 수동 레이아웃 프레임 - 자식들이 절대 위치 지정됨
            return self._html_container(node, children_html, [])

    def _html_text(self, node: Dict[str, Any]) -> str:
        """TEXT 노드를 HTML로 변환"""
        # 레이아웃 스타일 빌드
        builder = self._create_html_builder(node)
        builder.add_position_styles(node)
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

    def _html_container(self, node: Dict[str, Any], children: str, additional_styles: List[str]) -> str:
        """HTML 컨테이너 생성"""
        # 크기가 0인 컨테이너 무시
        width = node.get("width", 0)
        height = node.get("height", 0)
        if width <= 0 or height <= 0:
            return children

        builder = self._create_html_builder(node)
        builder.add_position_styles(node)
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

        # HTML 태그 결정
        tag = "div"
        src = ""

        # 이미지 처리
        if self.image_processor and self.image_processor.node_has_image_fill(node):
            file_key = node.get("file_key")
            node_id = node.get("node_id")
            image_result = self.image_processor.process_image_node(
                node, self.settings, file_key=file_key, node_id=node_id
            )
            
            if image_result.get("background_image"):
                # 배경 이미지로 사용
                builder.add_style("background-image", image_result["background_image"])
                builder.add_style("background-size", "cover")
            elif image_result.get("src_attr"):
                # img 태그로 사용
                tag = "img"
                src = image_result["src_attr"]
        else:
            # 기존 이미지 처리로 폴백
            fills = node.get("fills", [])
            if fills and any(fill.get("type") == "IMAGE" for fill in fills):
                if not children:
                    tag = "img"
                    src = ' src="https://via.placeholder.com/150"'
                else:
                    builder.add_style("background-image", "url(https://via.placeholder.com/150)")

        if children:
            return f'\n<{tag} class="{class_name}"{src}>{indent_string(children)}\n</{tag}>'
        else:
            return f'\n<{tag} class="{class_name}"{src}></{tag}>'

    def _html_section(self, node: Dict[str, Any]) -> str:
        """SECTION 노드를 HTML로 변환"""
        children = node.get("children", [])
        children_html = self._html_widget_generator(children)

        builder = self._create_html_builder(node)
        builder.add_size_styles(node)
        builder.add_position_styles(node)
        builder.add_background_styles(node)

        class_name = generate_unique_class_name(node, self.class_name_counters)
        css_styles = builder.build()
        self.css_collection[class_name] = css_styles

        if children_html:
            return f'\n<div class="{class_name}">{indent_string(children_html)}\n</div>'
        else:
            return f'\n<div class="{class_name}"></div>'

    def _html_line(self, node: Dict[str, Any]) -> str:
        """LINE 노드를 HTML로 변환"""
        builder = self._create_html_builder(node)
        builder.add_position_styles(node)
        builder.add_border_styles(node)

        class_name = generate_unique_class_name(node, self.class_name_counters)
        css_styles = builder.build()
        self.css_collection[class_name] = css_styles

        return f'\n<div class="{class_name}"></div>'

    def _html_wrap_svg(self, node: Dict[str, Any]) -> str:
        """SVG 콘텐츠 래핑"""
        class_name = generate_unique_class_name(node, self.class_name_counters)
        builder = self._create_html_builder(node)
        builder.add_position_styles(node)
        css_styles = builder.build()
        self.css_collection[class_name] = css_styles

        svg_content = node.get("svg")
        if not svg_content:
            # 플레이스홀더 SVG
            svg_content = f'''<svg width="{node.get('width', 24)}" height="{node.get('height', 24)}" viewBox="0 0 24 24" fill="none">
                <rect width="24" height="24" fill="#ddd"/>
                <text x="12" y="12" text-anchor="middle" dy=".3em" font-size="8">SVG</text>
            </svg>'''

        return f'\n<div class="{class_name}">{svg_content}</div>'

    def _html_auto_layout_props(self, node: Dict[str, Any]) -> List[str]:
        """자동 레이아웃 CSS 속성 생성"""
        styles = []
        layout_mode = node.get("layoutMode", "NONE")

        if layout_mode == "HORIZONTAL":
            styles.append("display: flex")
            styles.append("flex-direction: row")
        elif layout_mode == "VERTICAL":
            styles.append("display: flex")
            styles.append("flex-direction: column")

        # 간격 추가
        item_spacing = node.get("itemSpacing", 0)
        if item_spacing > 0:
            styles.append(f"gap: {item_spacing}px")

        # 정렬 추가
        primary_align = node.get("primaryAxisAlignItems", "MIN")
        counter_align = node.get("counterAxisAlignItems", "MIN")

        align_mapping = {
            "MIN": "flex-start",
            "CENTER": "center",
            "MAX": "flex-end"
        }

        if layout_mode == "HORIZONTAL":
            styles.append(f"justify-content: {align_mapping.get(primary_align, 'flex-start')}")
            styles.append(f"align-items: {align_mapping.get(counter_align, 'flex-start')}")
        elif layout_mode == "VERTICAL":
            styles.append(f"justify-content: {align_mapping.get(primary_align, 'flex-start')}")
            styles.append(f"align-items: {align_mapping.get(counter_align, 'flex-start')}")

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

        return [{
            "text": text_with_breaks,
            "styles": css_styles,
            "openTypeFeatures": {}
        }]

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

body {
    font-family: system-ui, -apple-system, sans-serif;
    line-height: 1.6;
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

    def _add_warning(self, message: str):
        """경고 메시지 추가"""
        if message not in self.warnings:
            self.warnings.append(message)

    def get_warnings(self) -> List[str]:
        """모든 경고 가져오기"""
        return self.warnings.copy()


def generate_html_from_nodes(nodes: List[Dict[str, Any]], settings: Optional[Dict[str, Any]] = None) -> Dict[str, str]:
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