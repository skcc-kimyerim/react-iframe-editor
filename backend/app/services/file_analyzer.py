"""
파일 메타데이터 추출 및 분석 서비스
TypeScript/TSX 파일의 구조, 컴포넌트, 훅, 타입 정의 등을 분석
"""
import re
from typing import Dict, List, Optional, Set
from pathlib import Path
import logging

logger = logging.getLogger("app.file_analyzer")

class ComponentInfo:
    """컴포넌트 정보를 담는 클래스"""
    def __init__(self, name: str, file_path: str):
        self.name = name
        self.file_path = file_path
        self.props: List[str] = []
        self.hooks: List[str] = []
        self.imports: List[str] = []
        self.exports: List[str] = []
        self.children_components: List[str] = []
        self.is_default_export = False
        self.description = ""

class FileMetadata:
    """파일 메타데이터를 담는 클래스"""
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.file_type = self._detect_file_type(file_path)
        self.components: List[ComponentInfo] = []
        self.hooks: List[str] = []
        self.types: List[str] = []
        self.interfaces: List[str] = []
        self.imports: Dict[str, List[str]] = {}  # module -> imported items
        self.exports: List[str] = []
        self.dependencies: Set[str] = set()
        self.file_size = 0
        self.line_count = 0
        
    def _detect_file_type(self, file_path: str) -> str:
        """파일 확장자에 따른 타입 결정"""
        ext = Path(file_path).suffix.lower()
        type_map = {
            '.tsx': 'tsx',
            '.ts': 'typescript',
            '.jsx': 'jsx', 
            '.js': 'javascript',
            '.css': 'css',
            '.json': 'json'
        }
        return type_map.get(ext, 'unknown')

class FileAnalyzer:
    """파일 분석기 메인 클래스"""
    
    def __init__(self, project_root: str):
        self.project_root = Path(project_root)
        self.file_cache: Dict[str, FileMetadata] = {}
        
    def analyze_file(self, file_path: str) -> Optional[FileMetadata]:
        """단일 파일 분석"""
        try:
            full_path = self.project_root / file_path
            if not full_path.exists():
                logger.warning(f"파일이 존재하지 않습니다: {file_path}")
                return None
                
            # 캐시 확인
            if file_path in self.file_cache:
                return self.file_cache[file_path]
                
            metadata = FileMetadata(file_path)
            content = full_path.read_text(encoding='utf-8')
            
            # 기본 정보 수집
            metadata.file_size = len(content)
            metadata.line_count = len(content.splitlines())
            
            # 파일 타입별 분석
            if metadata.file_type in ['tsx', 'jsx']:
                self._analyze_react_file(content, metadata)
            elif metadata.file_type in ['typescript', 'javascript']:
                self._analyze_js_ts_file(content, metadata)
                
            # 캐시에 저장
            self.file_cache[file_path] = metadata
            return metadata
            
        except Exception as e:
            logger.error(f"파일 분석 오류 {file_path}: {str(e)}")
            return None
    
    def _analyze_react_file(self, content: str, metadata: FileMetadata):
        """React/TSX 파일 분석"""
        # Import 문 분석
        self._extract_imports(content, metadata)
        
        # 컴포넌트 추출
        self._extract_components(content, metadata)
        
        # 훅 사용 분석
        self._extract_hooks(content, metadata)
        
        # 타입/인터페이스 추출
        self._extract_types_interfaces(content, metadata)
        
        # Export 문 분석
        self._extract_exports(content, metadata)
    
    def _analyze_js_ts_file(self, content: str, metadata: FileMetadata):
        """JavaScript/TypeScript 파일 분석"""
        self._extract_imports(content, metadata)
        self._extract_exports(content, metadata)
        self._extract_types_interfaces(content, metadata)
        
        # 함수 추출
        self._extract_functions(content, metadata)
    
    def _extract_imports(self, content: str, metadata: FileMetadata):
        """Import 문 추출"""
        # ES6 import 패턴
        import_patterns = [
            r"import\s+(.+?)\s+from\s+['\"](.+?)['\"]",  # import ... from "..."
            r"import\s+['\"](.+?)['\"]",  # import "..."
        ]
        
        for pattern in import_patterns:
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                if len(match.groups()) == 2:
                    imported_items = match.group(1).strip()
                    module = match.group(2).strip()
                    
                    if module not in metadata.imports:
                        metadata.imports[module] = []
                    
                    # 의존성 추가
                    metadata.dependencies.add(module)
                    
                    # Import 항목 파싱 (default, named imports)
                    if imported_items:
                        # {} 내부의 named imports 추출
                        named_match = re.search(r'\{(.+?)\}', imported_items)
                        if named_match:
                            named_imports = [item.strip() for item in named_match.group(1).split(',')]
                            metadata.imports[module].extend(named_imports)
                        
                        # Default import 추출
                        default_match = re.search(r'^([^{,]+)', imported_items)
                        if default_match:
                            default_import = default_match.group(1).strip()
                            if default_import and default_import != '':
                                metadata.imports[module].append(f"default:{default_import}")
    
    def _extract_components(self, content: str, metadata: FileMetadata):
        """React 컴포넌트 추출"""
        # 함수형 컴포넌트 패턴들 (더 간단하고 정확하게)
        component_patterns = [
            # export const ComponentName = () => {
            r"export\s+const\s+([A-Z][a-zA-Z0-9_]*)\s*=\s*\(",
            # export const ComponentName: React.FC<Props> = 
            r"export\s+const\s+([A-Z][a-zA-Z0-9_]*)\s*:\s*React\.FC",
            # export function ComponentName() {
            r"export\s+function\s+([A-Z][a-zA-Z0-9_]*)\s*\(",
            # const ComponentName = () => { ... export default ComponentName
            r"const\s+([A-Z][a-zA-Z0-9_]*)\s*=\s*\(",
            # const ComponentName: React.FC<Props> = 
            r"const\s+([A-Z][a-zA-Z0-9_]*)\s*:\s*React\.FC",
            # function ComponentName() { ... export default ComponentName  
            r"function\s+([A-Z][a-zA-Z0-9_]*)\s*\(",
            # export default function ComponentName
            r"export\s+default\s+function\s+([A-Z][a-zA-Z0-9_]*)\s*\("
        ]
        
        found_components = set()  # 중복 방지
        
        for pattern in component_patterns:
            matches = re.finditer(pattern, content, re.MULTILINE)
            for match in matches:
                component_name = match.group(1)
                
                # 중복 확인
                if component_name in found_components:
                    continue
                found_components.add(component_name)
                    
                component = ComponentInfo(component_name, metadata.file_path)
                
                # Props 추출 (간단한 패턴) - 구조분해할당 확인
                props_patterns = [
                    rf"(?:function\s+{component_name}|const\s+{component_name}\s*=.*?)\s*\(\s*\{{\s*([^}}]+)\s*\}}",
                    rf"(?:function\s+{component_name}|const\s+{component_name}\s*=.*?)\s*\(\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:"  # props: Type 형태
                ]
                
                for props_pattern in props_patterns:
                    props_match = re.search(props_pattern, content)
                    if props_match:
                        props_str = props_match.group(1)
                        if '{' not in props_str:  # 단일 props 매개변수
                            component.props = [props_str.strip()]
                        else:
                            component.props = [prop.strip() for prop in props_str.split(',') if prop.strip()]
                        break
                
                # Default export 확인
                if (re.search(rf"export\s+default\s+{component_name}", content) or 
                    re.search(rf"export\s+default\s+function\s+{component_name}", content)):
                    component.is_default_export = True
                
                metadata.components.append(component)
    
    def _extract_hooks(self, content: str, metadata: FileMetadata):
        """React 훅 사용 추출"""
        hook_patterns = [
            r"use[A-Z][a-zA-Z0-9_]*\s*\(",  # React hooks
            r"(?:const|let|var)\s+\[[^]]+\]\s*=\s*(use[A-Z][a-zA-Z0-9_]*)\s*\(",  # const [state, setState] = useState()
        ]
        
        hooks = set()
        for pattern in hook_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                hook_name = match.group(1) if len(match.groups()) > 0 else match.group(0).split('(')[0].strip()
                hooks.add(hook_name)
        
        metadata.hooks = list(hooks)
    
    def _extract_types_interfaces(self, content: str, metadata: FileMetadata):
        """타입과 인터페이스 추출"""
        # Interface 추출
        interface_pattern = r"(?:export\s+)?interface\s+([A-Z][a-zA-Z0-9_]*)"
        interface_matches = re.finditer(interface_pattern, content)
        for match in interface_matches:
            metadata.interfaces.append(match.group(1))
        
        # Type 추출
        type_pattern = r"(?:export\s+)?type\s+([A-Z][a-zA-Z0-9_]*)\s*="
        type_matches = re.finditer(type_pattern, content)
        for match in type_matches:
            metadata.types.append(match.group(1))
    
    def _extract_exports(self, content: str, metadata: FileMetadata):
        """Export 문 추출"""
        export_patterns = [
            r"export\s+(?:default\s+)?(?:const|function|class)\s+([a-zA-Z_][a-zA-Z0-9_]*)",
            r"export\s+\{([^}]+)\}",
            r"export\s+default\s+([a-zA-Z_][a-zA-Z0-9_]*)"
        ]
        
        for pattern in export_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                if '{' in match.group(0):  # Named exports
                    exports_str = match.group(1)
                    exports = [exp.strip() for exp in exports_str.split(',') if exp.strip()]
                    metadata.exports.extend(exports)
                else:
                    metadata.exports.append(match.group(1))
    
    def _extract_functions(self, content: str, metadata: FileMetadata):
        """함수 추출 (일반 JS/TS 파일용)"""
        function_patterns = [
            r"(?:export\s+)?(?:async\s+)?function\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*\(",
            r"(?:export\s+)?(?:const|let|var)\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*=\s*(?:async\s+)?\([^)]*\)\s*=>"
        ]
        
        functions = []
        for pattern in function_patterns:
            matches = re.finditer(pattern, content)
            for match in matches:
                functions.append(match.group(1))
        
        # functions를 exports에 추가 (이미 추출된 exports와 중복 제거)
        for func in functions:
            if func not in metadata.exports:
                metadata.exports.append(func)
    
    def analyze_project_structure(self, src_path: str = "src") -> Dict[str, FileMetadata]:
        """프로젝트 전체 구조 분석"""
        src_dir = self.project_root / src_path
        if not src_dir.exists():
            logger.warning(f"소스 디렉토리가 존재하지 않습니다: {src_path}")
            return {}
        
        analyzed_files = {}
        
        # 지원하는 파일 확장자
        supported_extensions = {'.tsx', '.ts', '.jsx', '.js'}
        
        # 재귀적으로 파일 탐색
        for file_path in src_dir.rglob('*'):
            if file_path.is_file() and file_path.suffix in supported_extensions:
                relative_path = str(file_path.relative_to(self.project_root))
                metadata = self.analyze_file(relative_path)
                if metadata:
                    analyzed_files[relative_path] = metadata
        
        return analyzed_files
    
    def get_dependency_graph(self) -> Dict[str, List[str]]:
        """의존성 그래프 생성"""
        dependency_graph = {}
        
        for file_path, metadata in self.file_cache.items():
            dependencies = []
            
            # 내부 모듈 의존성만 추출 (상대 경로 import)
            for module in metadata.dependencies:
                if module.startswith('.') or module.startswith('/'):
                    dependencies.append(module)
            
            dependency_graph[file_path] = dependencies
        
        return dependency_graph
    
    def find_related_files(self, target_file: str, max_depth: int = 2) -> List[str]:
        """특정 파일과 관련된 파일들 찾기"""
        if target_file not in self.file_cache:
            return []
        
        related_files = set()
        target_metadata = self.file_cache[target_file]
        
        # 1. 직접 import하는 파일들
        for module in target_metadata.dependencies:
            if module.startswith('.'):
                # 상대 경로를 절대 경로로 변환
                resolved_path = self._resolve_relative_import(target_file, module)
                if resolved_path in self.file_cache:
                    related_files.add(resolved_path)
        
        # 2. 이 파일을 import하는 파일들
        for file_path, metadata in self.file_cache.items():
            for module in metadata.dependencies:
                resolved_path = self._resolve_relative_import(file_path, module)
                if resolved_path == target_file:
                    related_files.add(file_path)
        
        # 3. 같은 컴포넌트 이름을 사용하는 파일들
        target_components = {comp.name for comp in target_metadata.components}
        for file_path, metadata in self.file_cache.items():
            file_components = {comp.name for comp in metadata.components}
            if target_components & file_components:  # 교집합이 있으면
                related_files.add(file_path)
        
        return list(related_files)
    
    def _resolve_relative_import(self, current_file: str, import_path: str) -> str:
        """상대 경로 import를 절대 경로로 변환"""
        if not import_path.startswith('.'):
            return import_path
        
        current_dir = Path(current_file).parent
        target_path = current_dir / import_path
        
        # 확장자가 없으면 추가 시도
        possible_extensions = ['.tsx', '.ts', '.jsx', '.js', '/index.tsx', '/index.ts', '/index.jsx', '/index.js']
        
        for ext in possible_extensions:
            test_path = str(target_path) + ext
            if test_path in self.file_cache:
                return test_path
        
        return str(target_path)
    
    def get_project_summary(self) -> Dict:
        """프로젝트 전체 요약 정보"""
        total_files = len(self.file_cache)
        total_components = sum(len(metadata.components) for metadata in self.file_cache.values())
        
        file_types = {}
        for metadata in self.file_cache.values():
            file_types[metadata.file_type] = file_types.get(metadata.file_type, 0) + 1
        
        # 가장 많이 사용되는 컴포넌트/라이브러리
        all_dependencies = set()
        for metadata in self.file_cache.values():
            all_dependencies.update(metadata.dependencies)
        
        external_deps = [dep for dep in all_dependencies if not dep.startswith('.')]
        
        return {
            "total_files": total_files,
            "total_components": total_components,
            "file_types": file_types,
            "external_dependencies": external_deps[:10],  # 상위 10개
            "dependency_graph": self.get_dependency_graph()
        }