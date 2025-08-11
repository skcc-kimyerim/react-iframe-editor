# lab/figma2html/src/react_generator.py
"""
OpenRouter-Powered React Component Generator
Figma JSON 데이터를 OpenRouter(Claude)를 이용해 React TSX 컴포넌트로 변환
"""

import asyncio
import json
import os
import re
from typing import Dict

from .llm_service import get_llm_service


class ReactComponentGenerator:
    """LLM 기반 Figma JSON을 React TSX 컴포넌트로 변환하는 클래스"""

    def __init__(self):
        self.component_name = ""
        self.llm_service = get_llm_service()

    async def generate_from_json_file(
        self, json_path: str, output_dir: str = "components"
    ) -> tuple[bool, str]:
        """JSON 파일에서 React 컴포넌트 생성"""
        try:
            with open(json_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            # 첫 번째 노드의 document를 분석
            first_node_key = list(data["nodes"].keys())[0]
            document = data["nodes"][first_node_key]["document"]

            return await self.generate_component(document, output_dir)

        except Exception as e:
            return False, f"JSON 파일 처리 오류: {str(e)}"

    async def generate_component(self, document: Dict, output_dir: str) -> tuple[bool, str]:
        """Document 구조를 분석해서 LLM으로 React 컴포넌트 생성"""
        try:
            component_name = self._sanitize_component_name(
                document.get("name", "Component")
            )
            self.component_name = component_name

            return await self._generate_react_component(document, output_dir)

        except Exception as e:
            return False, f"LLM 컴포넌트 생성 오류: {str(e)}"

    async def _generate_react_component(
        self, document: Dict, output_dir: str
    ) -> tuple[bool, str]:
        """LLM을 사용해서 컴포넌트 생성 - Figma JSON 직접 전달"""
        try:
            model_info = self.llm_service.get_model_info()
            print(
                f"🤖 {model_info['provider']} ({model_info['model']})로 Figma JSON에서 React 컴포넌트 생성 중..."
            )

            # Figma JSON을 직접 LLM에 전달해서 컴포넌트 생성
            component_code = await self._generate_react_from_figma_json(document)

            # 파일 저장
            return self._save_component_file(component_code, output_dir)

        except Exception as e:
            print(f"❌ LLM 컴포넌트 생성 실패: {e}")
            return False, f"LLM 컴포넌트 생성 실패: {str(e)}"

    async def _generate_react_from_figma_json(self, figma_document: Dict) -> str:
        """Figma JSON 데이터를 직접 LLM에 전달해서 React TSX 컴포넌트 생성"""

        # 시스템 프롬프트 (역할과 핵심 원칙)
        system_context = f"""
🎯 당신은 최고 수준의 React TypeScript 개발자입니다.
컴포넌트 이름: {self.component_name}

🚨 절대 규칙 (위반 시 실패):
1. 절대 구체적인 텍스트를 하드코딩하지 마세요
2. 모든 콘텐츠는 props를 통해서만 전달
3. 기본값은 빈 배열([]) 또는 빈 문자열('') 사용
4. TypeScript + tailwind css 필수 사용

💡 최우선 설계 원칙:
- 재사용성 최우선: 다양한 상황에서 사용할 수 있는 유연한 컴포넌트
- 동적 데이터 지원: props로 모든 내용 제어 가능
- 상태 관리: 필요한 경우 내부 상태와 외부 제어 props 모두 지원
"""

        # 메인 프롬프트
        prompt = f"""
{system_context}

=== 작업 지시사항 ===
다음 Figma JSON 데이터를 바탕으로 완전한 React TSX 컴포넌트를 생성해주세요:

=== Figma JSON 데이터 ===
{json.dumps(figma_document, ensure_ascii=False, indent=2)}

=== 기능적 의도 분석 ===
컴포넌트 이름과 Figma 구조를 분석해서 의도된 기능을 추론하고 구현하세요:

**스크롤 관련 컴포넌트**: ScrollList, VirtualList, ScrollView, InfiniteScroll
→ `height` 또는 `maxHeight` prop 추가, `overflow-y: auto` 스타일 적용, `onScroll` 이벤트 핸들러, 가상화가 필요한 경우 `react-window` 또는 유사 로직 고려

**검색/필터 컴포넌트**: SearchableList, FilterableTable, SearchInput
→ `searchTerm`, `onSearch` props, `filteredItems` 로직, 검색 결과 하이라이트 기능

**무한 스크롤 컴포넌트**: InfiniteScroll, LoadMoreList
→ `hasMore`, `isLoading` props, `onLoadMore` 콜백, 스크롤 위치 감지 로직

**상태 관리 컴포넌트**: StatefulButton, ToggleSwitch, Checkbox
→ 내부 상태와 제어 상태 모두 지원, `value`, `defaultValue`, `onChange` 패턴

**레이아웃 컴포넌트**: ResponsiveGrid, FlexContainer, MasonryLayout
→ 반응형 브레이크포인트, 동적 열/행 계산, 미디어 쿼리 적용

**데이터 표시 컴포넌트**: DataTable, Timeline, Chart
→ 복잡한 데이터 구조 처리, 정렬, 페이지네이션 기능, 로딩/에러 상태

=== 하드코딩 금지 규칙 ===
❌ 절대 금지:
- 구체적인 텍스트 하드코딩
- 예시 데이터를 기본값으로 사용
- 고정된 배열이나 객체 데이터

올바른 기본값:
- 배열 props: 빈 배열 `[]`
- 문자열 props: 빈 문자열 `''` 또는 의미있는 플레이스홀더
- 불린 props: `false` 또는 적절한 기본 상태
- 객체 props: 빈 객체 `{{}}` 또는 null

=== 🔧 필수 기술 요구사항 ===
1. **TypeScript 사용 필수**
2. **tailwind css 사용**
3. **함수형 컴포넌트 + React Hooks**
4. **완전한 Props 인터페이스 정의**
5. **모든 prop에 대한 기본값 설정**
6. **접근성 고려** (ARIA 속성, 키보드 탐색)
7. **반응형 디자인**

=== Props 설계 가이드라인 ===
1. **콘텐츠 제어**: 텍스트, 아이콘, 이미지 등 모든 콘텐츠를 props로 받기
2. **상태 제어**: isDisabled, isActive, isSelected, isLoading 등 상태 props
3. **스타일 제어**: variant, size, color 등 스타일 변형 props
4. **동작 제어**: onClick, onChange, onHover 등 이벤트 핸들러 props
5. **배열 데이터**: 리스트/메뉴 타입인 경우 items 배열로 동적 콘텐츠 지원
6. **기능별 props**: 추론된 기능에 맞는 전용 props 추가

=== 컴포넌트 유형별 특별 고려사항 ===

**버튼 컴포넌트**: variant(primary/secondary/ghost), size(small/medium/large), isDisabled, isLoading, startIcon, endIcon, children

**메뉴/리스트 컴포넌트**: items 배열(빈 배열 기본값), onItemClick, selectedItem, isMultiSelect, isDisabled, maxHeight, onScroll

**스크롤 리스트**: items(빈 배열), height, maxHeight, isVirtualized, onScroll, hasMore, onLoadMore, isLoading

**카드 컴포넌트**: header, body, footer를 각각 props로, actions 배열(빈 배열 기본값)

**입력 컴포넌트**: value(''), onChange, placeholder(''), error(''), helperText(''), isRequired(false)

**검색 컴포넌트**: searchTerm(''), onSearch, placeholder(''), filteredItems, highlightMatch

**모달/다이얼로그**: isOpen(false), onClose, title(''), content(''), actions 배열(빈 배열 기본값)

**데이터 테이블**: data(빈 배열), columns(빈 배열), sortBy, sortOrder, onSort, pagination

=== 빈 상태 처리 ===
- 필수 props가 비어있을 때의 처리 로직 포함
- 빈 배열일 때 적절한 대체 UI 또는 안내 메시지
- 데이터가 없어도 컴포넌트가 깨지지 않도록 방어 코딩
- 로딩 상태와 에러 상태 UI 고려

=== 시각적 재현 요구사항 ===
- Figma의 색상, 크기, 레이아웃을 정확히 반영
- 레이아웃 모드 (HORIZONTAL, VERTICAL, NONE)를 고려한 CSS flexbox 사용
- 색상 정보 (fills, strokes)를 정확히 CSS로 변환
- 텍스트 스타일 (fontSize, fontWeight, fontFamily)를 반영
- 간격 정보 (padding, itemSpacing)를 정확히 적용
- 테두리 반지름 (cornerRadius)과 테두리 (strokes) 적용
- 스크롤 필요 시 적절한 높이 제한과 overflow 처리

=== 성능 최적화 고려사항 ===
- 큰 리스트의 경우 가상화 (virtualization) 고려
- 무한 스크롤의 경우 Intersection Observer 사용
- 검색/필터링의 경우 디바운싱 적용
- 복잡한 계산은 useMemo 사용
- 이벤트 핸들러는 useCallback 사용

=== 코드 품질 요구사항 ===
- TypeScript 타입 안전성 100%
- ESLint/Prettier 규칙 준수
- 성능 최적화 (React.memo, useMemo, useCallback 적절히 사용)
- 에러 처리 및 예외 상황 고려
- JSDoc 주석으로 Props 설명 (사용 예시 포함)
- 테스트하기 쉬운 구조

=== JSDoc 예시 가이드 ===
```typescript
/**
 * @example
 * // 기본 스크롤 리스트
 * <ScrollList 
 *   items={{[
 *     {{ id: '1', name: 'Item 1' }},
 *     {{ id: '2', name: 'Item 2' }}
 *   ]}}
 *   height={{300}}
 *   onScroll={{handleScroll}}
 * />
 * 
 * // 무한 스크롤
 * <InfiniteScrollList
 *   items={{items}}
 *   hasMore={{true}}
 *   isLoading={{false}}
 *   onLoadMore={{loadMore}}
 * />
 * 
 * // 비활성화 상태
 * <List isDisabled={{true}} items={{[]}} />
 */
```

=== 📄 출력 형식 ===
다음 구조로 완전한 TSX 파일을 생성하세요:

1. **Import 구문** (필요한 React hooks 포함)
2. **TypeScript 인터페이스 정의** (상세한 JSDoc 포함)
3. **tailwind css 정의** (기능에 맞는 스타일링)
4. **메인 컴포넌트 함수** (최소한의 기본값, 기능 로직, JSX)
5. **export default**

 **최종 확인사항:**
- 컴포넌트 이름과 구조를 분석해서 의도된 기능을 구현했는가?
- 절대 하드코딩하지 않고 기본값은 빈 값으로 설정했는가?
- 모든 콘텐츠가 props를 통해 제어 가능한가?

완전한 TSX 파일 내용만 출력하세요. 마크다운 블록이나 추가 설명은 포함하지 마세요.
"""

        try:
            model_info = self.llm_service.get_model_info()

            messages = [
                {
                    "role": "system",
                    "content": "당신은 최고 수준의 React TypeScript 개발자입니다. Figma JSON 데이터를 정확히 분석해서 시각적으로 동일한 React 컴포넌트를 생성해주세요. \
                        tailwind css를 사용하여 프로덕션 레벨의 코드를 작성하세요. Figma의 레이아웃, 색상, 타이포그래피, 간격 등 모든 시각적 요소를 정확히 반영해야 합니다.",
                },
                {"role": "user", "content": prompt},
            ]

            return await self.llm_service.generate_completion(messages)

        except Exception as e:
            print(f"❌ LLM 코드 생성 실패: {e}")
            raise

    def generate_test_page_from_prompt(self, prompt_data: dict) -> tuple[bool, str]:
        """LLM(OpenRouter/Claude)에게 TestPage.tsx 전체 코드를 생성 요청"""
        try:
            figma_page = prompt_data.get("figma_page", {})
            available_components = prompt_data.get("available_components", [])
            # 프롬프트 설계 (TestPage.tsx 전체 코드 생성)
            prompt = f"""
당신은 최고 수준의 React TypeScript 개발자입니다.
아래 Figma 페이지 JSON과 사용 가능한 컴포넌트 목록을 참고하여, 실제 서비스에서 사용할 수 있는 완전한 TestPage.tsx 파일을 생성하세요.

=== Figma 페이지 JSON ===
{json.dumps(figma_page, ensure_ascii=False, indent=2)}

=== 사용 가능한 컴포넌트 목록 (import해서 사용) ===
{available_components}

- 반드시 TypeScript + tailwind css 사용
- 컴포넌트는 import해서 사용 (없는 경우 직접 구현)
- 완전한 TSX 파일만 출력 (마크다운 블록 없이)
- 실제 서비스에서 바로 사용할 수 있는 수준의 코드로 작성
"""
            tsx_code = asyncio.run(
                self._generate_react_from_figma_json_with_prompt(prompt)
            )
            return True, tsx_code
        except Exception as e:
            return False, str(e)

    async def _generate_react_from_figma_json_with_prompt(self, prompt: str) -> str:
        try:
            messages = [
                {
                    "role": "system",
                    "content": "당신은 최고 수준의 React TypeScript 개발자입니다. Figma JSON 데이터를 정확히 분석해서 시각적으로 동일한 React 컴포넌트를 생성해주세요. tailwind css를 사용하여 프로덕션 레벨의 코드를 작성하세요. \
                    Figma의 레이아웃, 색상, 타이포그래피, 간격 등 모든 시각적 요소를 정확히 반영해야 합니다.",
                },
                {"role": "user", "content": prompt},
            ]
            return await self.llm_service.generate_completion(messages)
        except Exception as e:
            print(f"❌ LLM 코드 생성 실패: {e}")
            raise

    async def _generate_react_from_html_css_with_prompt(self, prompt: str) -> str:
        """
        LLM에게 HTML/CSS를 분석해서 시각적으로 동일한 React 컴포넌트를 생성하도록 요청하는 함수
        """
        try:
            messages = [
                {
                    "role": "system",
                    "content": (
                        "당신은 최고 수준의 React TypeScript 개발자입니다. "
                        "아래 HTML/CSS 구조를 정확히 분석해서 시각적으로 동일한 React 컴포넌트를 생성해주세요. "
                        "tailwind css를 사용하여 프로덕션 레벨의 코드를 작성하세요. "
                        "레이아웃, 색상, 타이포그래피, 간격 등 모든 시각적 요소를 정확히 반영해야 합니다."
                    ),
                },
                {"role": "user", "content": prompt},
            ]
            return await self.llm_service.generate_completion(messages)
        except Exception as e:
            print(f"❌ LLM 코드 생성 실패: {e}")
            raise

    def _sanitize_component_name(self, name: str) -> str:
        """컴포넌트 이름을 유효한 React 컴포넌트 이름으로 변환"""
        # 특수문자 제거 및 PascalCase 변환
        name = re.sub(r"[^a-zA-Z0-9\s]", "", name)
        words = name.split()
        return "".join(word.capitalize() for word in words) or "Component"

    def _save_component_file(
        self, component_code: str, output_dir: str
    ) -> tuple[bool, str]:
        """컴포넌트 파일 저장"""
        try:
            os.makedirs(output_dir, exist_ok=True)
            file_path = os.path.join(output_dir, f"{self.component_name}.tsx")

            # 코드에서 마크다운 블록 제거
            cleaned_code = component_code
            if cleaned_code.startswith("```"):
                lines = cleaned_code.split("\n")
                # 첫 번째와 마지막 줄에서 ```제거
                if lines[0].startswith("```"):
                    lines = lines[1:]
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                cleaned_code = "\n".join(lines)

            with open(file_path, "w", encoding="utf-8") as f:
                f.write(cleaned_code)

            return True, f"React 컴포넌트가 {file_path}에 저장되었습니다"

        except Exception as e:
            return False, f"파일 저장 오류: {str(e)}"
