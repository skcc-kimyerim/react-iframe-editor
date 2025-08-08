"""
Image Processing Module
Handles image fills, Base64 conversion, and placeholder generation
Ported from FigmaToCode images.ts
"""

import base64
import requests
import logging
from io import BytesIO
from typing import Dict, Any, Optional, List
from .figma_api_client import FigmaApiClient



class ImageProcessor:
    """Image processing logic ported from FigmaToCode"""
    
    PLACEHOLDER_IMAGE_DOMAIN = "https://placehold.co"
    
    def __init__(self, api_client: FigmaApiClient):
        self.api_client = api_client
        self.warnings: List[str] = []

    def get_placeholder_image(self, width: int, height: int = -1) -> str:
        """
        Generate placeholder image URL
        
        Args:
            width: Image width
            height: Image height (defaults to width if not specified)
            
        Returns:
            Placeholder image URL
        """
        _width = int(width)
        _height = int(height if height >= 0 else width)
        
        return f"{self.PLACEHOLDER_IMAGE_DOMAIN}/{_width}x{_height}"

    def node_has_image_fill(self, node: Dict[str, Any]) -> bool:
        """
        Check if a node has image fills
        
        Args:
            node: The node to check
            
        Returns:
            True if node has image fills
        """
        fills = node.get("fills", [])
        if not isinstance(fills, list):
            return False
            
        return any(fill.get("type") == "IMAGE" for fill in fills)

    def get_image_fills(self, node: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Get all image fills from a node
        
        Args:
            node: The node to extract image fills from
            
        Returns:
            List of image fill objects
        """
        try:
            fills = node.get("fills", [])
            if not isinstance(fills, list):
                return []
                
            return [fill for fill in fills if fill.get("type") == "IMAGE"]
        except Exception:
            return []

    def node_has_multiple_fills(self, node: Dict[str, Any]) -> bool:
        """
        Check if a node has multiple fills
        
        Args:
            node: The node to check
            
        Returns:
            True if node has multiple fills
        """
        fills = node.get("fills", [])
        return isinstance(fills, list) and len(fills) > 1

    def export_node_as_base64_png(self, node: Dict[str, Any], exclude_children: bool = False, file_key: Optional[str] = None, node_id: Optional[str] = None) -> Optional[str]:
        """
        Export a node as Base64 PNG using Figma API
        Args:
            node: The node to export
            exclude_children: Whether to exclude children during export
            file_key: Figma file key (required)
            node_id: Node ID (required)
        Returns:
            Base64 encoded PNG string or None if failed
        """
        # Check if already converted
        base64_data = node.get("base64")
        if base64_data:
            return base64_data

        # file_key, node_id가 없으면 placeholder 반환
        if not file_key or not node_id:
            return self._create_placeholder_base64(node.get("width", 150), node.get("height", 150))

        try:
            # 1. Figma API로 이미지 URL 요청
            images = self.api_client.get_images(file_key, [node_id], format="png")
            if not images or node_id not in images or not images[node_id]:
                self._add_warning(f"No image URL returned for node {node_id}")
                return self._create_placeholder_base64(node.get("width", 150), node.get("height", 150))
            image_url = images[node_id]

            # 2. 이미지 다운로드
            resp = requests.get(image_url)
            if resp.status_code != 200:
                self._add_warning(f"Failed to download image for node {node_id}")
                return self._create_placeholder_base64(node.get("width", 150), node.get("height", 150))
            image_bytes = resp.content

            # 3. base64 변환
            base64_png = self._image_bytes_to_base64(image_bytes)
            node["base64"] = base64_png
            return base64_png
        except Exception as e:
            logging.error(f"Error exporting node as Base64 PNG: {str(e)}")
            return self._create_placeholder_base64(node.get("width", 150), node.get("height", 150))

    def _create_placeholder_base64(self, width: int, height: int) -> str:
        """
        Create a Base64 encoded placeholder image
        
        Args:
            width: Image width
            height: Image height
            
        Returns:
            Base64 encoded image data URI
        """
        # This is a simple 1x1 transparent PNG in base64
        # In a real implementation, you might want to generate actual images
        transparent_png_b64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg=="
        
        return f"data:image/png;base64,{transparent_png_b64}"

    def _image_bytes_to_base64(self, image_bytes: bytes) -> str:
        """
        Convert image bytes to Base64 data URI
        
        Args:
            image_bytes: Raw image bytes
            
        Returns:
            Base64 encoded data URI
        """
        # Encode binary data to base64
        b64_string = base64.b64encode(image_bytes).decode('utf-8')
        
        return f"data:image/png;base64,{b64_string}"

    def create_canvas_image_url(self, width: int, height: int) -> str:
        """
        Create a canvas-based image URL (fallback to placeholder)
        
        Args:
            width: Image width
            height: Image height
            
        Returns:
            Image URL
        """
        # In a browser environment, this would create a canvas
        # For Python, we'll fall back to placeholder
        return self.get_placeholder_image(width, height)

    def process_image_node(self, node: Dict[str, Any], settings: Dict[str, Any], file_key: Optional[str] = None, node_id: Optional[str] = None) -> Dict[str, str]:
        """
        Process a node with image fills
        Args:
            node: The node to process
            settings: Processing settings
            file_key: Figma file key
            node_id: Node ID
        Returns:
            Dict with image URL and other processing info
        """
        result = {
            "url": "",
            "tag": "div",
            "src_attr": ""
        }
        
        if not self.node_has_image_fill(node):
            return result
        
        width = node.get("width", 150)
        height = node.get("height", 150)
        has_children = "children" in node and len(node.get("children", [])) > 0
        
        # file_key, node_id가 없으면 노드에서 추출
        fk = file_key or node.get("file_key")
        nid = node_id or node.get("node_id")
        
        # Check if we should embed images
        if settings.get("embedImages", False):
            img_url = self.export_node_as_base64_png(node, has_children, file_key=fk, node_id=nid)
        else:
            img_url = self.get_placeholder_image(width, height)
        
        result["url"] = img_url or ""
        
        # Decide on HTML structure
        if has_children:
            # Use as background image
            result["tag"] = "div"
            result["background_image"] = f"url({result['url']})"
        else:
            # Use as img tag
            result["tag"] = "img"
            result["src_attr"] = f' src="{result["url"]}"'
        
        return result

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


def create_image_processor(api_client: FigmaApiClient) -> ImageProcessor:
    """Factory function to create image processor"""
    return ImageProcessor(api_client) 