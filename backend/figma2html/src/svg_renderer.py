"""
SVG Renderer Module
Handles SVG rendering and color variable processing
Ported from FigmaToCode altNodeUtils.ts
"""

import re
import requests
import logging

from typing import Dict, Any, Optional, List
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
                self._add_warning(f"Failed to export SVG for {node.get('name', 'unnamed')}")
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
            logging.error(f"Error rendering SVG for {node.get('type', 'unknown')}:{node.get('id', 'no-id')}")
            logging.error(f"Error: {str(error)}")

        return node

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
                        return resp.text
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

    def _process_svg_colors(self, svg_content: str, color_mappings: Dict[str, Dict[str, str]]) -> str:
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
        
        def replace_color_attribute(match):
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
        
        processed_svg = re.sub(color_attribute_regex, replace_color_attribute, processed_svg)
        
        # Also handle style attributes with fill: or stroke: properties
        style_regex = r'style="([^"]*)(?:(fill|stroke):\s*([^;"]*))([;"]*)([^"]*)"'
        
        def replace_style_attribute(match):
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

    def _add_warning(self, message: str):
        """Add a warning message"""
        if message not in self.warnings:
            self.warnings.append(message)

    def get_warnings(self) -> List[str]:
        """Get all warning messages"""
        return self.warnings.copy()

    def clear_warnings(self):
        """Clear all warning messages"""
        self.warnings.clear()


def create_svg_renderer(api_client: FigmaApiClient) -> SVGRenderer:
    """Factory function to create SVG renderer"""
    return SVGRenderer(api_client) 