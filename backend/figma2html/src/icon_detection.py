"""
Icon Detection Module
Detects if a Figma node is likely an icon based on structure and properties
Ported from FigmaToCode iconDetection.ts
"""

import logging
from typing import Dict, Any, List, Set, Tuple


class IconDetection:
    """Icon detection logic ported from FigmaToCode"""
    
    # Node types that are allowed in icons
    ICON_PRIMITIVE_TYPES: Set[str] = {
        "RECTANGLE", "ELLIPSE", "POLYGON", "STAR", "LINE"
    }
    
    ICON_COMPLEX_VECTOR_TYPES: Set[str] = {
        "VECTOR", "BOOLEAN_OPERATION"
    }
    
    # Node types that disqualify a node from being an icon
    DISALLOWED_ICON_TYPES: Set[str] = {
        "TEXT", "FRAME", "COMPONENT", "INSTANCE", "COMPONENT_SET"
    }
    
    # Child types that disqualify a node from being an icon
    DISALLOWED_CHILD_TYPES: Set[str] = {
        "TEXT", "FRAME", "COMPONENT", "INSTANCE", "COMPONENT_SET"
    }

    def is_likely_icon(self, node: Dict[str, Any], log_details: bool = False) -> bool:
        """
        Analyzes a Figma node to determine if it's likely an icon
        
        Args:
            node: The Figma node to evaluate
            log_details: Set to true to print debug information
            
        Returns:
            True if the node is likely an icon, false otherwise
        """
        info = [f"Node: {node.get('name', 'unnamed')} ({node.get('type', 'unknown')}, ID: {node.get('id', 'no-id')})"]
        result = False
        reason = ""

        # 1. Initial Filtering (Disallowed Types First)
        if node.get("type") in self.DISALLOWED_ICON_TYPES:
            reason = f"Disallowed Type: {node.get('type')}"
            result = False
        # 2. Check for SVG Export Settings (Only if not disallowed)
        elif self._has_svg_export_settings(node):
            reason = "Has SVG export settings"
            result = True
        # 3. Dimension Check
        elif not self._has_valid_dimensions(node):
            reason = "Invalid dimensions"
            result = False
        # 4. Simple Vector Types (Always Icons)
        elif node.get("type") in self.ICON_COMPLEX_VECTOR_TYPES:
            reason = f"Simple vector type: {node.get('type')}"
            result = True
        # 5. Size Check for other types
        elif not self._is_typical_icon_size(node):
            reason = f"Too large for icon: {node.get('width', 0)}x{node.get('height', 0)}"
            result = False
        # 6. Container Type Analysis
        elif node.get("type") == "GROUP":
            child_result = self._check_children_recursively(node.get("children", []))
            if child_result["has_disallowed_child"]:
                reason = "Contains disallowed child types"
                result = False
            elif child_result["has_valid_content"]:
                reason = "Group with valid icon content"
                result = True
            else:
                reason = "Group with no valid icon content"
                result = False
        # 7. Primitive Shape Analysis
        elif node.get("type") in self.ICON_PRIMITIVE_TYPES:
            reason = f"Primitive icon type: {node.get('type')}"
            result = True
        else:
            reason = f"Unhandled node type: {node.get('type')}"
            result = False

        if log_details:
            info.append(f"Result: {result}")
            info.append(f"Reason: {reason}")
            logging.debug("\n".join(info))

        return result

    def _has_svg_export_settings(self, node: Dict[str, Any]) -> bool:
        """Checks if a node has export settings for SVG"""
        export_settings = node.get("exportSettings", [])
        return any(setting.get("format") == "SVG" for setting in export_settings)

    def _has_valid_dimensions(self, node: Dict[str, Any]) -> bool:
        """Check if node has valid dimensions"""
        width = node.get("width", 0)
        height = node.get("height", 0)
        return width > 0 and height > 0

    def _is_typical_icon_size(self, node: Dict[str, Any], max_size: int = 64) -> bool:
        """
        Checks if the node dimensions are typical for an icon
        
        Args:
            node: The node to check
            max_size: Maximum size for an icon (default 64px)
            
        Returns:
            True if within typical icon size range
        """
        width = node.get("width", 0)
        height = node.get("height", 0)
        
        # Only check if dimensions exceed the maximum allowed size
        return width <= max_size and height <= max_size

    def _check_children_recursively(self, children: List[Dict[str, Any]]) -> Dict[str, bool]:
        """
        Recursively checks the children of a container node
        
        Returns:
            Dict with has_disallowed_child and has_valid_content flags
        """
        has_disallowed_child = False
        has_valid_content = False

        for child in children:
            if child.get("visible", True) is False:
                continue  # Skip invisible children

            if child.get("type") in self.DISALLOWED_CHILD_TYPES:
                has_disallowed_child = True
                break  # Found disallowed type, no need to check further

            if (child.get("type") in self.ICON_COMPLEX_VECTOR_TYPES or 
                child.get("type") in self.ICON_PRIMITIVE_TYPES):
                has_valid_content = True
            elif child.get("type") == "GROUP" and "children" in child:
                # Recursively check children of groups
                group_result = self._check_children_recursively(child.get("children", []))
                if group_result["has_disallowed_child"]:
                    has_disallowed_child = True
                    break  # Disallowed child found in nested group
                if group_result["has_valid_content"]:
                    has_valid_content = True  # Valid content found in nested group

        return {
            "has_disallowed_child": has_disallowed_child,
            "has_valid_content": has_valid_content
        }


# Global instance for easy usage
icon_detector = IconDetection()


def is_likely_icon(node: Dict[str, Any], log_details: bool = False) -> bool:
    """Convenience function for icon detection"""
    return icon_detector.is_likely_icon(node, log_details) 