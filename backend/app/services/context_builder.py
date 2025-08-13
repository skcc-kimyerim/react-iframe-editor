"""
컨텍스트 빌더 서비스
사용자 질문에 따라 관련 파일들을 자동으로 선택하고 컨텍스트를 구성
"""
import re
from typing import List, Dict, Optional, Tuple
from .file_analyzer import FileAnalyzer, FileMetadata
import logging

logger = logging.getLogger("app.context_builder")

class ContextBuilder:
    """컨텍스트 빌더 메인 클래스"""
    
    def __init__(self, file_analyzer: FileAnalyzer):
        self.file_analyzer = file_analyzer
        
        # 질문 유형별 키워드 매핑
        self.question_keywords = {
            "component": ["컴포넌트", "component", "UI", "버튼", "button", "카드", "card", "모달", "modal"],
            "hook": ["훅", "hook", "useState", "useEffect", "use"],
            "style": ["스타일", "style", "CSS", "디자인", "색상", "color", "레이아웃", "layout"],
            "function": ["함수", "function", "로직", "계산", "처리"],
            "type": ["타입", "type", "interface", "인터페이스", "모델"],
            "routing": ["라우팅", "routing", "페이지", "page", "경로", "route"],
            "state": ["상태", "state", "데이터", "data", "관리"],
            "api": ["API", "서버", "server", "통신", "요청", "request"]
        }
    
    def build_context_for_question(
        self, 
        question: str, 
        selected_file: Optional[str] = None,
        max_files: int = 5
    ) -> Dict:
        """
        질문에 대한 컨텍스트 구성
        
        Args:
            question: 사용자 질문
            selected_file: 현재 선택된 파일
            max_files: 포함할 최대 파일 수
        
        Returns:
            컨텍스트 정보 딕셔너리
        """
        # 1. 질문 분석
        question_type = self._analyze_question_type(question)
        mentioned_entities = self._extract_mentioned_entities(question)
        
        # 2. 관련 파일 선택
        relevant_files = self._select_relevant_files(
            question, question_type, mentioned_entities, selected_file, max_files
        )
        
        # 3. 컨텍스트 요약 생성
        context_summary = self._generate_context_summary(relevant_files, question_type)
        
        return {
            "question_type": question_type,
            "mentioned_entities": mentioned_entities,
            "relevant_files": relevant_files,
            "context_summary": context_summary,
            "file_count": len(relevant_files)
        }
    
    def _analyze_question_type(self, question: str) -> str:
        """질문 타입 분석"""
        question_lower = question.lower()
        
        # 각 타입별 점수 계산
        type_scores = {}
        for question_type, keywords in self.question_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword.lower() in question_lower:
                    score += 1
            type_scores[question_type] = score
        
        # 가장 높은 점수의 타입 반환
        if type_scores:
            return max(type_scores, key=type_scores.get)
        return "general"
    
    def _extract_mentioned_entities(self, question: str) -> List[str]:
        """질문에서 언급된 엔티티 추출 (컴포넌트명, 파일명 등)"""
        entities = []
        
        # 1. 대문자로 시작하는 단어들 (컴포넌트명 가능성)
        component_pattern = r'\b[A-Z][a-zA-Z0-9_]*\b'
        components = re.findall(component_pattern, question)
        entities.extend(components)
        
        # 2. 파일 경로나 확장자가 있는 것들
        file_pattern = r'\b[\w/.-]+\.(tsx?|jsx?|css|json)\b'
        files = re.findall(file_pattern, question)
        entities.extend([f[0] for f in files])  # 확장자 제외한 파일명
        
        # 3. 따옴표나 백틱으로 감싸진 텍스트
        quoted_pattern = r'["`\']([\w/.-]+)["`\']'
        quoted = re.findall(quoted_pattern, question)
        entities.extend(quoted)
        
        # 중복 제거 후 반환
        return list(set(entities))
    
    def _select_relevant_files(
        self, 
        question: str, 
        question_type: str, 
        mentioned_entities: List[str],
        selected_file: Optional[str],
        max_files: int
    ) -> List[Dict]:
        """관련 파일들 선택"""
        
        scored_files = []
        
        # 캐시된 모든 파일에 대해 점수 계산
        for file_path, metadata in self.file_analyzer.file_cache.items():
            score = self._calculate_file_relevance_score(
                metadata, question, question_type, mentioned_entities
            )
            
            if score > 0:
                scored_files.append({
                    "file_path": file_path,
                    "metadata": metadata,
                    "score": score,
                    "is_selected": file_path == selected_file
                })
        
        # 점수 기준으로 정렬
        scored_files.sort(key=lambda x: (-x["score"], x["file_path"]))
        
        # 선택된 파일을 최우선으로
        if selected_file:
            selected_items = [f for f in scored_files if f["is_selected"]]
            other_items = [f for f in scored_files if not f["is_selected"]]
            scored_files = selected_items + other_items
        
        # 상위 파일들만 선택
        selected_files = scored_files[:max_files]
        
        # 관련 파일 추가 (의존성 기반)
        for file_info in selected_files[:2]:  # 상위 2개 파일의 관련 파일들
            related_files = self.file_analyzer.find_related_files(file_info["file_path"], max_depth=1)
            for related_file in related_files[:2]:  # 각 파일당 최대 2개 관련 파일
                if len(selected_files) >= max_files:
                    break
                if not any(f["file_path"] == related_file for f in selected_files):
                    if related_file in self.file_analyzer.file_cache:
                        selected_files.append({
                            "file_path": related_file,
                            "metadata": self.file_analyzer.file_cache[related_file],
                            "score": 0.5,  # 관련 파일은 낮은 점수
                            "is_selected": False,
                            "is_related": True
                        })
        
        return selected_files[:max_files]
    
    def _calculate_file_relevance_score(
        self, 
        metadata: FileMetadata, 
        question: str, 
        question_type: str, 
        mentioned_entities: List[str]
    ) -> float:
        """파일 관련도 점수 계산"""
        score = 0.0
        question_lower = question.lower()
        file_name = metadata.file_path.lower()
        
        # 1. 파일명 매칭
        for entity in mentioned_entities:
            if entity.lower() in file_name:
                score += 2.0
        
        # 2. 컴포넌트명 매칭
        for component in metadata.components:
            component_name_lower = component.name.lower()
            if component_name_lower in question_lower:
                score += 3.0
            for entity in mentioned_entities:
                if entity.lower() == component_name_lower:
                    score += 2.0
        
        # 3. 질문 타입별 점수
        type_bonus = {
            "component": 1.0 if metadata.components else 0,
            "hook": 1.0 if metadata.hooks else 0,
            "type": 1.0 if metadata.types or metadata.interfaces else 0,
            "style": 1.0 if metadata.file_type == 'css' else 0
        }
        score += type_bonus.get(question_type, 0)
        
        # 4. 키워드 매칭 (파일 내용 기반)
        if question_type in self.question_keywords:
            keywords = self.question_keywords[question_type]
            for keyword in keywords:
                # 파일의 exports, components, hooks에서 키워드 검색
                all_names = (
                    [comp.name for comp in metadata.components] +
                    metadata.hooks +
                    metadata.exports +
                    metadata.types +
                    metadata.interfaces
                )
                
                for name in all_names:
                    if keyword.lower() in name.lower():
                        score += 0.5
        
        # 5. 파일 타입별 가중치
        type_weights = {
            'tsx': 1.0,
            'jsx': 0.9,
            'ts': 0.7,
            'js': 0.6,
            'css': 0.3
        }
        score *= type_weights.get(metadata.file_type, 0.5)
        
        return score
    
    def _generate_context_summary(self, relevant_files: List[Dict], question_type: str) -> str:
        """컨텍스트 요약 생성"""
        if not relevant_files:
            return "관련 파일을 찾을 수 없습니다."
        
        summary_parts = []
        
        # 파일 타입별 그룹화
        file_groups = {}
        for file_info in relevant_files:
            file_type = file_info["metadata"].file_type
            if file_type not in file_groups:
                file_groups[file_type] = []
            file_groups[file_type].append(file_info)
        
        # 각 그룹별 요약
        for file_type, files in file_groups.items():
            type_name_map = {
                'tsx': 'React 컴포넌트',
                'jsx': 'React 컴포넌트', 
                'ts': 'TypeScript',
                'js': 'JavaScript',
                'css': 'CSS 스타일'
            }
            type_name = type_name_map.get(file_type, file_type.upper())
            
            file_names = [file_info["file_path"].split('/')[-1] for file_info in files]
            summary_parts.append(f"{type_name} 파일: {', '.join(file_names)}")
        
        # 주요 컴포넌트들
        all_components = []
        for file_info in relevant_files:
            all_components.extend([comp.name for comp in file_info["metadata"].components])
        
        if all_components:
            summary_parts.append(f"주요 컴포넌트: {', '.join(set(all_components[:5]))}")
        
        return " | ".join(summary_parts)
    
    def get_file_content_summary(self, file_path: str, max_length: int = 500) -> str:
        """파일 내용 요약 (토큰 효율성을 위해)"""
        if file_path not in self.file_analyzer.file_cache:
            return ""
        
        metadata = self.file_analyzer.file_cache[file_path]
        
        summary_parts = []
        
        # 1. 파일 기본 정보
        summary_parts.append(f"파일: {file_path} ({metadata.file_type})")
        
        # 2. 주요 컴포넌트
        if metadata.components:
            components_info = []
            for comp in metadata.components[:3]:  # 최대 3개
                props_str = f"props: {', '.join(comp.props[:3])}" if comp.props else ""
                components_info.append(f"{comp.name}({props_str})")
            summary_parts.append(f"컴포넌트: {'; '.join(components_info)}")
        
        # 3. 주요 exports
        if metadata.exports:
            summary_parts.append(f"Exports: {', '.join(metadata.exports[:5])}")
        
        # 4. 주요 imports
        if metadata.imports:
            ext_imports = [module for module in metadata.imports.keys() if not module.startswith('.')]
            if ext_imports:
                summary_parts.append(f"주요 의존성: {', '.join(ext_imports[:3])}")
        
        # 5. 타입/인터페이스
        if metadata.types or metadata.interfaces:
            all_types = metadata.types + metadata.interfaces
            summary_parts.append(f"타입: {', '.join(all_types[:3])}")
        
        summary = " | ".join(summary_parts)
        
        # 길이 제한
        if len(summary) > max_length:
            summary = summary[:max_length-3] + "..."
        
        return summary
    
    def create_optimized_context(
        self, 
        question: str, 
        selected_file: Optional[str] = None
    ) -> str:
        """질문에 최적화된 컨텍스트 생성 (LLM용)"""
        
        context_info = self.build_context_for_question(question, selected_file)
        
        context_parts = [
            f"질문 타입: {context_info['question_type']}",
            f"컨텍스트 요약: {context_info['context_summary']}"
        ]
        
        # 관련 파일들의 요약 정보
        for file_info in context_info["relevant_files"][:3]:  # 최대 3개 파일
            file_summary = self.get_file_content_summary(file_info["file_path"])
            if file_summary:
                context_parts.append(f"\n--- {file_summary}")
        
        # 언급된 엔티티가 있으면 추가
        if context_info["mentioned_entities"]:
            context_parts.append(f"언급된 요소: {', '.join(context_info['mentioned_entities'])}")
        
        return "\n".join(context_parts)