"""
CSS Style Builder
Build CSS styles for Figma nodes with comprehensive styling support
"""

import logging
import math
from typing import Any, Dict, Optional


class CSSStyleBuilder:
    """Build CSS styles for nodes"""

    def __init__(self):
        self.styles: Dict[str, str] = {}

    def add_style(self, property: str, value: str) -> "CSSStyleBuilder":
        """Add a CSS property-value pair"""
        if value and value != "0" and value != "none":
            self.styles[property] = value
        return self

    def add_styles_from_dict(self, style_dict: Dict[str, str]) -> "CSSStyleBuilder":
        """Add multiple styles from a dictionary"""
        for prop, value in style_dict.items():
            self.add_style(prop, value)
        return self

    def add_position_styles(
        self, node: Dict[str, Any], parent_node: Optional[Dict[str, Any]] = None
    ) -> "CSSStyleBuilder":
        """Add position and size styles based on layout context"""
        # Add size
        self._add_size_styles(
            node, parent_node, node.get("width", 0), node.get("height", 0)
        )

        # Add position based on parent layout context
        self._add_positioning_styles(node, parent_node)

        # Add child auto layout styles if parent has auto layout
        if parent_node and parent_node.get("layoutMode", "NONE") != "NONE":
            self.add_child_auto_layout_styles(node, parent_node)

        # Add transform for rotation if present
        # 새로운 transform 구조 처리
        if "transform" in node and node["transform"]:
            transform_info = node["transform"]
            if "rotate" in transform_info:
                deg = transform_info["rotate"]
                self.add_style("transform", f"rotate({deg}deg)")
        else:
            # 기존 rotation 필드 처리 (하위 호환성)
            rotation = node.get("rotation", 0)
            if rotation and abs(rotation) > 0.01:
                # rotation 값이 라디안이므로 degree로 변환
                deg = math.degrees(rotation)
                self.add_style("transform", f"rotate({deg}deg)")

        return self

    def _add_positioning_styles(
        self, node: Dict[str, Any], parent_node: Optional[Dict[str, Any]]
    ) -> None:
        """Add positioning styles based on layout context"""
        x = node.get("x", 0)
        y = node.get("y", 0)

        # Determine positioning type based on layout context
        layout_positioning = node.get("layoutPositioning", "AUTO")
        parent_layout_mode = (
            parent_node.get("layoutMode", "NONE") if parent_node else "NONE"
        )

        # Force absolute positioning for manual layout or explicit absolute positioning
        node_name = node.get("name", "unknown")
        parent_name = parent_node.get("name", "unknown") if parent_node else "None"
        logging.debug(
            f"[POSITIONING DEBUG] Node: '{node_name}' | Parent: '{parent_name}' | Parent Layout Mode: '{parent_layout_mode}' | Node Layout Positioning: '{layout_positioning}'"
        )

        if layout_positioning == "ABSOLUTE" or not parent_node:
            self.add_style("position", "absolute")
            if x != 0:
                self.add_style("left", f"{x}px")
            if y != 0:
                self.add_style("top", f"{y}px")
        elif parent_layout_mode == "NONE":
            self.add_style("position", "absolute")
            if x != 0:
                self.add_style("left", f"{x}px")
            if y != 0:
                self.add_style("top", f"{y}px")
        else:
            # Auto layout child - don't add absolute positioning
            # Position will be handled by flex/grid layout
            # child 의 absolute 처리 위해 relative 추가
            self.add_style("position", "relative")
            pass

    def _add_size_styles(
        self,
        node: Dict[str, Any],
        parent_node: Optional[Dict[str, Any]],
        width: float,
        height: float,
    ) -> None:
        """Add width and height styles"""
        if width > 0:
            self.add_style("width", f"{width}px")
        if height > 0:
            self.add_style("height", f"{height}px")

    def add_size_styles(self, node: Dict[str, Any]) -> "CSSStyleBuilder":
        """Add size styles (width and height)"""
        width = node.get("width", 0)
        height = node.get("height", 0)
        self._add_size_styles(node, None, width, height)
        return self

    def add_background_styles(self, node: Dict[str, Any]) -> "CSSStyleBuilder":
        """Add background styles from fills"""
        fills = node.get("fills", [])
        if not fills:
            return self

        # Take the first visible fill
        for fill in fills:
            if fill.get("visible", True):
                if fill.get("type") == "SOLID":
                    color = self._convert_color(fill.get("color", {}))
                    opacity = fill.get("opacity", 1.0)
                    if opacity < 1.0:
                        self.add_style("background-color", f"rgba({color}, {opacity})")
                    else:
                        self.add_style("background-color", f"rgb({color})")
                    break
                elif fill.get("type") == "GRADIENT_LINEAR":
                    gradient = self._convert_linear_gradient(fill)
                    if gradient:
                        self.add_style("background", gradient)
                    break
                elif fill.get("type") == "IMAGE":
                    # For images, we don't add background-image to CSS (handled in HTML)
                    # CSS에는 background-image를 추가하지 않음 (HTML에서 처리됨)
                    break

        return self

    def add_border_styles(self, node: Dict[str, Any]) -> "CSSStyleBuilder":
        """Add border styles from strokes"""
        strokes = node.get("strokes", [])
        stroke_weight = node.get("strokeWeight", 0)

        if strokes and stroke_weight > 0:
            stroke = strokes[0]  # Take first stroke
            if stroke.get("visible", True):
                color = self._convert_color(stroke.get("color", {}))
                opacity = stroke.get("opacity", 1.0)

                if opacity < 1.0:
                    border_color = f"rgba({color}, {opacity})"
                else:
                    border_color = f"rgb({color})"

                self.add_style("border", f"{stroke_weight}px solid {border_color}")

        # Add border radius if present
        return self.add_border_radius(node)

    def add_border_radius(self, node: Dict[str, Any]) -> "CSSStyleBuilder":
        """Add border radius styles"""
        # Handle different radius properties
        corner_radius = node.get("cornerRadius")
        if corner_radius is not None and corner_radius > 0:
            self.add_style("border-radius", f"{corner_radius}px")
            return self

        # Handle individual corner radii
        radii = []
        for corner in [
            "topLeftRadius",
            "topRightRadius",
            "bottomRightRadius",
            "bottomLeftRadius",
        ]:
            radius = node.get(corner, 0)
            radii.append(f"{radius}px")

        if any(r != "0px" for r in radii):
            self.add_style("border-radius", " ".join(radii))

        return self

    def add_text_styles(self, node: Dict[str, Any]) -> "CSSStyleBuilder":
        """Add text-specific styles"""
        style = node.get("style", {})

        # Font properties
        if "fontFamily" in style:
            self.add_style("font-family", f'"{style["fontFamily"]}", sans-serif')

        if "fontSize" in style:
            self.add_style("font-size", f"{style['fontSize']}px")

        if "fontWeight" in style:
            self.add_style("font-weight", str(style["fontWeight"]))

        if "lineHeight" in style:
            line_height = style["lineHeight"]
            if isinstance(line_height, dict):
                if line_height.get("unit") == "PIXELS":
                    self.add_style("line-height", f"{line_height.get('value', 1.2)}px")
                elif line_height.get("unit") == "PERCENT":
                    self.add_style(
                        "line-height", f"{line_height.get('value', 120) / 100}"
                    )
            elif isinstance(line_height, (int, float)):
                self.add_style("line-height", str(line_height))

        if "letterSpacing" in style:
            letter_spacing = style["letterSpacing"]
            if isinstance(letter_spacing, dict):
                if letter_spacing.get("unit") == "PIXELS":
                    self.add_style(
                        "letter-spacing", f"{letter_spacing.get('value', 0)}px"
                    )
                elif letter_spacing.get("unit") == "PERCENT":
                    # Convert percent to em
                    percent_value = letter_spacing.get("value", 0)
                    em_value = percent_value / 100
                    self.add_style("letter-spacing", f"{em_value}em")
            elif isinstance(letter_spacing, (int, float)):
                self.add_style("letter-spacing", f"{letter_spacing}px")

        # Text alignment
        text_align = node.get("textAlignHorizontal")
        if text_align:
            align_map = {
                "LEFT": "left",
                "CENTER": "center",
                "RIGHT": "right",
                "JUSTIFIED": "justify",
            }
            if text_align in align_map:
                self.add_style("text-align", align_map[text_align])

        # Text color from fills
        fills = node.get("fills", [])
        if fills:
            fill = fills[0]  # Take first fill
            if fill.get("type") == "SOLID":
                color = self._convert_color(fill.get("color", {}))
                opacity = fill.get("opacity", 1.0)
                if opacity < 1.0:
                    self.add_style("color", f"rgba({color}, {opacity})")
                else:
                    self.add_style("color", f"rgb({color})")

        return self

    def add_shadow_styles(self, node: Dict[str, Any]) -> "CSSStyleBuilder":
        """Add shadow styles from effects"""
        effects = node.get("effects", [])

        drop_shadows = []
        for effect in effects:
            if effect.get("type") == "DROP_SHADOW" and effect.get("visible", True):
                offset = effect.get("offset", {})
                x = offset.get("x", 0)
                y = offset.get("y", 0)
                blur = effect.get("radius", 0)
                color = self._convert_color(effect.get("color", {}))
                opacity = effect.get("color", {}).get("a", 1.0)

                if opacity < 1.0:
                    shadow_color = f"rgba({color}, {opacity})"
                else:
                    shadow_color = f"rgb({color})"

                drop_shadows.append(f"{x}px {y}px {blur}px {shadow_color}")

        if drop_shadows:
            self.add_style("box-shadow", ", ".join(drop_shadows))

        return self

    def add_opacity(self, node: Dict[str, Any]) -> "CSSStyleBuilder":
        """Add opacity if less than 1"""
        opacity = node.get("opacity", 1.0)
        if opacity < 1.0:
            self.add_style("opacity", str(opacity))
        return self

    def add_auto_layout_styles(self, node: Dict[str, Any]) -> "CSSStyleBuilder":
        """Add auto-layout styles based on Figma API spec"""
        layout_mode = node.get("layoutMode", "NONE")

        if layout_mode in ["HORIZONTAL", "VERTICAL"]:
            self._add_flex_layout_styles(node, layout_mode)
        elif layout_mode == "GRID":
            self._add_grid_layout_styles(node)

        return self

    def _add_flex_layout_styles(self, node: Dict[str, Any], layout_mode: str) -> None:
        """Add flexbox-based auto layout styles"""
        self.add_style("display", "flex")

        # Flex direction
        if layout_mode == "HORIZONTAL":
            self.add_style("flex-direction", "row")
        else:
            self.add_style("flex-direction", "column")

        # Item spacing (gap)
        item_spacing = node.get("itemSpacing", 0)
        if item_spacing > 0:
            self.add_style("gap", f"{item_spacing}px")

        # Wrapping
        layout_wrap = node.get("layoutWrap", "NO_WRAP")
        if layout_wrap == "WRAP":
            self.add_style("flex-wrap", "wrap")
            # Counter axis spacing for wrapped content
            counter_axis_spacing = node.get("counterAxisSpacing", 0)
            if counter_axis_spacing > 0:
                self.add_style(
                    "row-gap" if layout_mode == "VERTICAL" else "column-gap",
                    f"{counter_axis_spacing}px",
                )

        # Primary axis alignment
        primary_align = node.get("primaryAxisAlignItems", "MIN")
        self._add_primary_axis_alignment(primary_align, layout_wrap)

        # Counter axis alignment
        counter_align = node.get("counterAxisAlignItems", "MIN")
        self._add_counter_axis_alignment(counter_align, layout_wrap)

        # Counter axis content alignment (for wrapped content)
        if layout_wrap == "WRAP":
            counter_align_content = node.get("counterAxisAlignContent", "AUTO")
            if counter_align_content != "AUTO":
                align_content_mapping = {"SPACE_BETWEEN": "space-between"}
                align_content = align_content_mapping.get(counter_align_content)
                if align_content:
                    self.add_style("align-content", align_content)

    def _add_grid_layout_styles(self, node: Dict[str, Any]) -> None:
        """Add CSS Grid-based auto layout styles"""
        self.add_style("display", "grid")

        # Grid template from Figma properties
        grid_columns_sizing = node.get("gridColumnsSizing", "")
        grid_rows_sizing = node.get("gridRowsSizing", "")

        if grid_columns_sizing:
            self.add_style("grid-template-columns", grid_columns_sizing)
        else:
            # Fallback to count-based grid
            grid_column_count = node.get("gridColumnCount", 1)
            self.add_style("grid-template-columns", f"repeat({grid_column_count}, 1fr)")

        if grid_rows_sizing:
            self.add_style("grid-template-rows", grid_rows_sizing)
        else:
            # Fallback to count-based grid
            grid_row_count = node.get("gridRowCount", 1)
            self.add_style("grid-template-rows", f"repeat({grid_row_count}, auto)")

        # Grid gaps
        grid_row_gap = node.get("gridRowGap", 0)
        grid_column_gap = node.get("gridColumnGap", 0)

        if grid_row_gap > 0 or grid_column_gap > 0:
            if grid_row_gap == grid_column_gap:
                self.add_style("gap", f"{grid_row_gap}px")
            else:
                self.add_style("row-gap", f"{grid_row_gap}px")
                self.add_style("column-gap", f"{grid_column_gap}px")

    def _add_primary_axis_alignment(self, primary_align: str, layout_wrap: str) -> None:
        """Add primary axis alignment styles"""
        align_mapping = {
            "MIN": "flex-start",
            "CENTER": "center",
            "MAX": "flex-end",
            "SPACE_BETWEEN": "space-between",
        }

        justify_content = align_mapping.get(primary_align, "flex-start")
        self.add_style("justify-content", justify_content)

    def _add_counter_axis_alignment(self, counter_align: str, layout_wrap: str) -> None:
        """Add counter axis alignment styles"""
        align_mapping = {
            "MIN": "flex-start",
            "CENTER": "center",
            "MAX": "flex-end",
            "BASELINE": "baseline",
        }

        align_items = align_mapping.get(counter_align, "flex-start")
        self.add_style("align-items", align_items)

    def add_child_auto_layout_styles(
        self, node: Dict[str, Any], parent_node: Optional[Dict[str, Any]] = None
    ) -> "CSSStyleBuilder":
        """Add auto-layout styles for child elements"""
        if not parent_node or parent_node.get("layoutMode") == "NONE":
            return self

        parent_layout_mode = parent_node.get("layoutMode")

        if parent_layout_mode in ["HORIZONTAL", "VERTICAL"]:
            self._add_flex_child_styles(node, parent_node)
        elif parent_layout_mode == "GRID":
            self._add_grid_child_styles(node, parent_node)

        return self

    def _add_flex_child_styles(
        self, node: Dict[str, Any], parent_node: Dict[str, Any]
    ) -> None:
        """Add flex child styles"""
        # Layout align (stretch behavior)
        layout_align = node.get("layoutAlign", "INHERIT")
        if layout_align == "STRETCH":
            self.add_style("align-self", "stretch")

        # Layout grow (flex-grow)
        layout_grow = node.get("layoutGrow", 0)
        if layout_grow > 0:
            self.add_style("flex-grow", str(layout_grow))
            self.add_style("flex-shrink", "0")

        # Layout sizing
        layout_sizing_horizontal = node.get("layoutSizingHorizontal", "FIXED")
        layout_sizing_vertical = node.get("layoutSizingVertical", "FIXED")

        parent_layout_mode = parent_node.get("layoutMode")

        # Apply sizing based on parent direction
        if parent_layout_mode == "HORIZONTAL":
            if layout_sizing_horizontal == "FILL":
                self.add_style("flex-grow", "1")
                self.add_style("flex-shrink", "0")
            elif layout_sizing_horizontal == "HUG":
                self.add_style("width", "auto")
                self.add_style("flex-shrink", "0")
        else:  # VERTICAL
            if layout_sizing_vertical == "FILL":
                self.add_style("flex-grow", "1")
                self.add_style("flex-shrink", "0")
            elif layout_sizing_vertical == "HUG":
                self.add_style("height", "auto")
                self.add_style("flex-shrink", "0")

    def _add_grid_child_styles(
        self, node: Dict[str, Any], parent_node: Dict[str, Any]
    ) -> None:
        """Add grid child styles"""
        # Grid positioning
        grid_column_anchor = node.get("gridColumnAnchorIndex", 0)
        grid_row_anchor = node.get("gridRowAnchorIndex", 0)
        grid_column_span = node.get("gridColumnSpan", 1)
        grid_row_span = node.get("gridRowSpan", 1)

        # Grid column placement
        if grid_column_span > 1:
            self.add_style(
                "grid-column", f"{grid_column_anchor + 1} / span {grid_column_span}"
            )
        else:
            self.add_style("grid-column-start", str(grid_column_anchor + 1))

        # Grid row placement
        if grid_row_span > 1:
            self.add_style("grid-row", f"{grid_row_anchor + 1} / span {grid_row_span}")
        else:
            self.add_style("grid-row-start", str(grid_row_anchor + 1))

        # Grid child alignment
        grid_horizontal_align = node.get("gridChildHorizontalAlign", "AUTO")
        grid_vertical_align = node.get("gridChildVerticalAlign", "AUTO")

        if grid_horizontal_align != "AUTO":
            align_mapping = {"MIN": "start", "CENTER": "center", "MAX": "end"}
            justify_self = align_mapping.get(grid_horizontal_align)
            if justify_self:
                self.add_style("justify-self", justify_self)

        if grid_vertical_align != "AUTO":
            align_mapping = {"MIN": "start", "CENTER": "center", "MAX": "end"}
            align_self = align_mapping.get(grid_vertical_align)
            if align_self:
                self.add_style("align-self", align_self)

    def add_layout_styles(self, node: Dict[str, Any]) -> "CSSStyleBuilder":
        """Add general layout styles"""
        return self.add_auto_layout_styles(node)

    def add_padding(self, node: Dict[str, Any]) -> "CSSStyleBuilder":
        """Add padding styles"""
        # Handle auto-layout padding
        if node.get("layoutMode") in ["HORIZONTAL", "VERTICAL"]:
            padding_left = node.get("paddingLeft", 0)
            padding_right = node.get("paddingRight", 0)
            padding_top = node.get("paddingTop", 0)
            padding_bottom = node.get("paddingBottom", 0)

            if any([padding_left, padding_right, padding_top, padding_bottom]):
                padding_values = [
                    f"{padding_top}px",
                    f"{padding_right}px",
                    f"{padding_bottom}px",
                    f"{padding_left}px",
                ]
                self.add_style("padding", " ".join(padding_values))

        return self

    def build(self) -> str:
        """Build the final CSS string"""
        if not self.styles:
            return ""

        style_parts = []
        for prop, value in self.styles.items():
            style_parts.append(f"{prop}: {value}")

        return "; ".join(style_parts)

    def build_dict(self) -> Dict[str, str]:
        """Build and return styles as dictionary"""
        return self.styles.copy()

    def _convert_color(self, color: Dict[str, Any]) -> str:
        """Convert Figma color to CSS rgb values"""
        r = int((color.get("r", 0) * 255))
        g = int((color.get("g", 0) * 255))
        b = int((color.get("b", 0) * 255))
        return f"{r}, {g}, {b}"

    def _convert_linear_gradient(self, fill: Dict[str, Any]) -> str:
        """Convert Figma linear gradient to CSS"""
        gradient_handles = fill.get("gradientHandlePositions", [])
        gradient_stops = fill.get("gradientStops", [])

        if len(gradient_handles) < 2 or not gradient_stops:
            return ""

        # Calculate angle (simplified)
        start = gradient_handles[0]
        end = gradient_handles[1]

        # For simplicity, assume 0deg for now
        angle = "0deg"

        # Build gradient stops
        stops = []
        for stop in gradient_stops:
            color = self._convert_color(stop.get("color", {}))
            position = stop.get("position", 0) * 100
            opacity = stop.get("color", {}).get("a", 1.0)

            if opacity < 1.0:
                stops.append(f"rgba({color}, {opacity}) {position}%")
            else:
                stops.append(f"rgb({color}) {position}%")

        if stops:
            return f"linear-gradient({angle}, {', '.join(stops)})"

        return ""

    def _should_use_absolute_position(
        self, node: Dict[str, Any], parent_node: Dict[str, Any]
    ) -> bool:
        """Determine if node should use absolute positioning"""
        if not parent_node:
            return False

        return parent_node.get("layoutMode") == "NONE"


def build_css_for_node(
    node: Dict[str, Any], parent_node: Optional[Dict[str, Any]] = None
) -> str:
    """
    Build CSS for a node (convenience function)

    Args:
        node: Figma node data
        parent_node: Parent node for context

    Returns:
        CSS string
    """
    builder = CSSStyleBuilder()

    return (
        builder.add_position_styles(node, parent_node)
        .add_background_styles(node)
        .add_border_styles(node)
        .add_text_styles(node)
        .add_shadow_styles(node)
        .add_opacity(node)
        .add_layout_styles(node)
        .add_padding(node)
        .build()
    )


if __name__ == "__main__":
    # Test the style builder
    test_node = {
        "type": "FRAME",
        "name": "Test Frame",
        "width": 400,
        "height": 300,
        "x": 20,
        "y": 20,
        "layoutMode": "VERTICAL",
        "itemSpacing": 10,
        "fills": [{"type": "SOLID", "color": {"r": 1, "g": 1, "b": 1}, "opacity": 1.0}],
        "cornerRadius": 8,
        "strokes": [
            {"type": "SOLID", "color": {"r": 0.8, "g": 0.8, "b": 0.8}, "opacity": 1.0}
        ],
        "strokeWeight": 1,
    }

    css = build_css_for_node(test_node)
    logging.info("Generated CSS:")
    logging.info(css)
