"""
Figma to Code - Python Implementation
Convert Figma designs to HTML/CSS using REST API
"""

__version__ = "1.0.0"
__author__ = "Figma to Code Python"

from .src.main import FigmaToCode, cli
from .src.figma_url_parser import parse_figma_url
from .src.figma_api_client import FigmaApiClient
from .src.json_node_converter import JsonNodeConverter
from .src.html_generator import HtmlGenerator
from .src.style_builder import CSSStyleBuilder, build_css_for_node
from .src import utils

__all__ = [
    "FigmaToCode",
    "cli",
    "parse_figma_url",
    "FigmaApiClient",
    "JsonNodeConverter",
    "HtmlGenerator",
    "CSSStyleBuilder",
    "build_css_for_node",
    "utils",
]
