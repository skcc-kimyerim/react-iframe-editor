"""
Common utility functions for Figma to Code conversion
"""

import re
import os
import json
from typing import Dict, Any, List, Optional


def sanitize_filename(filename: str) -> str:
    """
    파일명을 안전하게 변환
    
    Args:
        filename: 원본 파일명
        
    Returns:
        안전한 파일명
    """
    sanitized = re.sub(r'[<>:"/\\|?*]', "_", filename)
    sanitized = re.sub(r"\s+", "_", sanitized)
    sanitized = sanitized.strip("._")
    
    if not sanitized:
        sanitized = "figma_design"
        
    return sanitized


def generate_unique_class_name(node: Dict[str, Any], counters: Dict[str, int]) -> str:
    """
    노드에 대한 고유한 CSS 클래스명 생성
    
    Args:
        node: Figma 노드 데이터
        counters: 클래스명 카운터 딕셔너리
        
    Returns:
        고유한 CSS 클래스명
    """
    base_name = node.get("uniqueName") or node.get("name", "element")
    
    # 클래스명 정리
    clean_name = re.sub(r"[^a-zA-Z0-9_-]", "_", base_name).lower()
    clean_name = re.sub(r"_+", "_", clean_name)
    clean_name = clean_name.strip("_")

    if not clean_name or clean_name[0].isdigit():
        clean_name = f"element_{clean_name}"

    # 고유성 보장
    count = counters.get(clean_name, 0)
    counters[clean_name] = count + 1

    if count > 0:
        return f"{clean_name}_{count}"
    else:
        return clean_name


def indent_string(content: str, spaces: int = 2) -> str:
    """
    문자열 들여쓰기
    
    Args:
        content: 들여쓰기할 내용
        spaces: 공백 수
        
    Returns:
        들여쓰기된 문자열
    """
    if not content:
        return content

    indent = " " * spaces
    lines = content.split("\n")
    indented_lines = [indent + line if line.strip() else line for line in lines]
    return "\n".join(indented_lines)


def save_json_response(data: Any, output_dir: str = "output/responses") -> str:
    """
    JSON 응답을 파일로 저장
    
    Args:
        data: 저장할 데이터
        output_dir: 저장할 디렉토리
        
    Returns:
        저장된 파일 경로
    """
    os.makedirs(output_dir, exist_ok=True)
    
    # 기존 파일 개수 확인하여 번호 매기기
    existing_files = [f for f in os.listdir(output_dir) if f.startswith("response_")]
    counter = len(existing_files) + 1
    
    filename = os.path.join(output_dir, f"response_{counter}.json")
    
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    
    return filename


def extract_all_node_ids(node: Dict[str, Any]) -> List[str]:
    """
    노드 트리에서 모든 노드 ID 추출
    
    Args:
        node: 루트 노드
        
    Returns:
        모든 노드 ID 리스트
    """
    node_ids = []
    
    if "id" in node:
        node_ids.append(node["id"])
        
    if "children" in node:
        for child in node["children"]:
            node_ids.extend(extract_all_node_ids(child))
            
    return node_ids


def inject_metadata(node: Dict[str, Any], file_key: str, node_id: str = None) -> None:
    """
    노드 트리에 메타데이터 주입
    
    Args:
        node: 대상 노드
        file_key: Figma 파일 키
        node_id: 노드 ID (선택사항)
    """
    node["file_key"] = file_key
    if "id" in node:
        node["node_id"] = node["id"]
    elif node_id:
        node["node_id"] = node_id
    
    # 자식 노드에도 재귀 적용
    for child in node.get("children", []):
        inject_metadata(child, file_key)


def get_best_frame_from_page(page: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    페이지에서 가장 복잡한 프레임 선택
    
    Args:
        page: Figma 페이지 데이터
        
    Returns:
        선택된 프레임 또는 None
    """
    page_children = page.get("children", [])
    
    if not page_children:
        return None
    
    # 자식이 가장 많은 프레임 찾기
    best_frame = None
    max_children = 0

    for frame in page_children:
        frame_children = frame.get("children", [])
        if len(frame_children) > max_children:
            max_children = len(frame_children)
            best_frame = frame

    return best_frame or page_children[0] 