# lab/figma2html/src/react_generator.py
"""
OpenRouter-Powered React Component Generator
Figma JSON 데이터를 OpenRouter(Claude)를 이용해 React TSX 컴포넌트로 변환
"""

import asyncio
import json
import os
import re
import copy
from typing import Dict, Any, List

from .llm_service import get_llm_service


class ReactComponentGenerator:
    """LLM 기반 Figma JSON을 React TSX 컴포넌트로 변환하는 클래스"""

    def __init__(self):
        self.component_name = ""
        self.llm_service = get_llm_service()

    async def find_similar_component_in_selection(
        self,
        selection_document: Dict,
        guide_md_path: str = "./output/frontend/COMPONENTS_GUIDE.md",
        filter_components: bool = False,
        concurrency: int = 5,
    ) -> tuple[bool, List[Dict[str, Any]] | str]:
        """
        선택된 Figma 노드 트리에서 처리 대상 컴포넌트를 추출하고,
        각 컴포넌트에 대해 유사 컴포넌트를 판별합니다.

        반환: (성공 여부, [ { nodeName, nodeType, decision: { index, name, reason } }, ... ] | 오류메시지)
        """
        try:

            def _collect_components(
                node: Dict[str, Any],
                collected: List[Dict[str, Any]],
                is_nested_component: bool = False,
            ) -> None:
                node_type = node.get("type")
                if filter_components:
                    if node_type in ["COMPONENT", "INSTANCE", "COMPONENT_SET"]:
                        if not is_nested_component:
                            collected.append(node.copy())
                            return
                else:
                    if node_type in ["COMPONENT", "INSTANCE", "COMPONENT_SET"]:
                        width = node.get("width", 0)
                        height = node.get("height", 0)
                        if width > 10 and height > 10:
                            collected.append(node.copy())

                children = node.get("children", [])
                for child in children:
                    _collect_components(child, collected, False)

            collected_components: List[Dict[str, Any]] = []
            _collect_components(selection_document, collected_components, False)

            unique_components: List[Dict[str, Any]] = []
            seen_names = set()
            for component in collected_components:
                comp_name = component.get("name", "")
                if comp_name and comp_name not in seen_names:
                    seen_names.add(comp_name)
                    unique_components.append(component)
            unique_components.sort(
                key=lambda c: c.get("width", 0) * c.get("height", 0), reverse=True
            )

            if not unique_components:
                return True, []

            # 병렬 실행 (동시성 제한)
            semaphore = asyncio.Semaphore(max(1, int(concurrency)))

            async def process_node(
                node: Dict[str, Any], order_idx: int
            ) -> tuple[int, Dict[str, Any]]:
                async with semaphore:
                    ok, decision = await self._find_similar_component_async(
                        node, guide_md_path=guide_md_path
                    )
                    if not ok:
                        return order_idx, {
                            "nodeName": node.get("name", ""),
                            "nodeType": node.get("type", ""),
                            "error": str(decision),
                            "__component": copy.deepcopy(node),
                        }
                    return order_idx, {
                        "nodeName": node.get("name", ""),
                        "nodeType": node.get("type", ""),
                        "decision": decision,
                        "__component": copy.deepcopy(node),
                    }

            tasks = [
                process_node(node, idx) for idx, node in enumerate(unique_components)
            ]
            gathered = await asyncio.gather(*tasks)
            # 원래 순서를 보존하여 정렬
            gathered.sort(key=lambda x: x[0])
            # 결과 리스트와 컴포넌트 맵 분리
            components_by_index: Dict[int, Dict[str, Any]] = {}
            ordered_results: List[Dict[str, Any]] = []
            for idx, item in gathered:
                component = item.pop("__component", None)
                if component is not None:
                    components_by_index[idx] = component
                ordered_results.append(item)

            return True, {"results": ordered_results, "components": components_by_index}

        except Exception as e:
            return False, f"선택 영역 유사도 판별 실패: {str(e)}"

    def _is_similar_component(
        self, selection_result: Dict[str, Any]
    ) -> tuple[bool, Dict[str, Any] | str]:
        """
        find_similar_component_in_selection 결과에서 decision.index 기준으로 분리합니다.

        - index != -1: 카탈로그에 유사 컴포넌트가 있는 경우 → similar
        - index == -1: 유사 컴포넌트가 없어 새 컴포넌트로 판정된 경우 → new

        입력 형식:
          selection_result: { "results": [ ... ], "components": { ... } } 또는 [ ... ] 리스트

        반환 형식:
          (True, { "similar": [...], "new": [...] }) 또는 (False, 오류메시지)
        """
        try:
            results = (
                selection_result.get("results")
                if isinstance(selection_result, dict)
                else selection_result
            )
            components_map: Dict[int, Dict[str, Any]] = (
                selection_result.get("components", {})
                if isinstance(selection_result, dict)
                else {}
            )
            if not isinstance(results, list):
                return False, "selection_result 형식이 올바르지 않습니다."

            similar: List[Dict[str, Any]] = []
            new: List[Dict[str, Any]] = []

            for idx, item in enumerate(results):
                if not isinstance(item, dict):
                    new.append({"error": "invalid item", "raw": item})
                    continue
                decision = item.get("decision")
                index_val = (
                    decision.get("index") if isinstance(decision, dict) else None
                )
                enriched_item = dict(item)
                if idx in components_map:
                    enriched_item["__component"] = components_map[idx]
                if isinstance(index_val, int) and index_val != -1:
                    similar.append(enriched_item)
                else:
                    new.append(enriched_item)

            return True, {"similar": similar, "new": new}
        except Exception as e:
            return False, f"분류 실패: {str(e)}"

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

    async def _generate_react_component_with_reference(
        self, document: Dict, output_dir: str, reference_sources: Dict[str, str]
    ) -> tuple[bool, str]:
        """유사한 컴포넌트 소스코드를 프롬프트에 포함하여 컴포넌트 생성"""
        try:
            model_info = self.llm_service.get_model_info()
            print(
                f"🤖 {model_info['provider']} ({model_info['model']})로 Figma JSON에서 React 컴포넌트 생성 중... (with reference)"
            )

            component_code = await self._generate_react_from_figma_json_with_reference(
                document, reference_sources
            )
            return self._save_component_file(component_code, output_dir)
        except Exception as e:
            print(f"❌ LLM 컴포넌트 생성 실패(with reference): {e}")
            return False, f"LLM 컴포넌트 생성 실패(with reference): {str(e)}"

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
4. TypeScript + styled-components 필수 사용

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
2. **styled-components 사용** (import styled from 'styled-components')
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
3. **styled-components 정의** (기능에 맞는 스타일링)
4. **메인 컴포넌트 함수** (최소한의 기본값, 기능 로직, JSX)
5. **export default**

**최종 확인사항:**
- 컴포넌트 이름과 구조를 분석해서 의도된 기능을 구현했는가?
- 절대 하드코딩하지 않고 기본값은 빈 값으로 설정했는가?
- 모든 콘텐츠가 props를 통해 제어 가능한가?

완전한 TSX 파일 내용만 출력하세요. 마크다운 블록이나 추가 설명은 포함하지 마세요.
"""

        try:
            messages = [
                {
                    "role": "system",
                    "content": "당신은 최고 수준의 React TypeScript 개발자입니다. Figma JSON 데이터를 정확히 분석해서 시각적으로 동일한 React 컴포넌트를 생성해주세요. styled-components를 사용하여 프로덕션 레벨의 코드를 작성하세요. Figma의 레이아웃, 색상, 타이포그래피, 간격 등 모든 시각적 요소를 정확히 반영해야 합니다.",
                },
                {"role": "user", "content": prompt},
            ]

            return await self.llm_service.generate_completion(messages)

        except Exception as e:
            print(f"❌ LLM 코드 생성 실패: {e}")
            raise

    async def _generate_react_from_figma_json_with_prompt(self, prompt: str) -> str:
        try:
            messages = [
                {
                    "role": "system",
                    "content": "당신은 최고 수준의 React TypeScript 개발자입니다. Figma JSON 데이터를 정확히 분석해서 시각적으로 동일한 React 컴포넌트를 생성해주세요. styled-components를 사용하여 프로덕션 레벨의 코드를 작성하세요. Figma의 레이아웃, 색상, 타이포그래피, 간격 등 모든 시각적 요소를 정확히 반영해야 합니다.",
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
                        "styled-components를 사용하여 프로덕션 레벨의 코드를 작성하세요. "
                        "레이아웃, 색상, 타이포그래피, 간격 등 모든 시각적 요소를 정확히 반영해야 합니다."
                    ),
                },
                {"role": "user", "content": prompt},
            ]
            return await self.llm_service.generate_completion(messages)
        except Exception as e:
            print(f"❌ LLM 코드 생성 실패: {e}")
            raise

    async def _generate_react_from_figma_json_with_reference(
        self, figma_document: Dict, reference_sources: Dict[str, str]
    ) -> str:
        """참고 소스코드를 함께 제공하여 TSX 생성"""
        # 시스템 프롬프트 (역할과 핵심 원칙)
        system_context = f"""
🎯 당신은 최고 수준의 React TypeScript 개발자입니다.
컴포넌트 이름: {self.component_name}

🚨 절대 규칙 (위반 시 실패):
1. 절대 구체적인 텍스트를 하드코딩하지 마세요
2. 모든 콘텐츠는 props를 통해서만 전달
3. 기본값은 빈 배열([]) 또는 빈 문자열('') 사용
4. TypeScript + styled-components 필수 사용
"""

        # 참고 소스코드 섹션 구성
        ref_blocks: List[str] = []
        for fname, code in reference_sources.items():
            header = f"[reference: {fname}]"
            ref_blocks.append(f"{header}\n{code}\n")
        reference_section = (
            "\n=== 참고 컴포넌트 소스 코드 (가능하면 API/Props/구조를 재사용) ===\n"
            + "\n".join(ref_blocks)
            if ref_blocks
            else ""
        )

        prompt = f"""
{system_context}

=== 작업 지시사항 ===
다음 Figma JSON 데이터를 바탕으로 완전한 React TSX 컴포넌트를 생성해주세요.
가능하다면 참고 소스코드의 Props/구조/이벤트 시그니처를 최대한 재사용하고, 호환되지 않는 경우에는 합리적으로 확장/보완하세요.

=== Figma JSON 데이터 ===
{json.dumps(figma_document, ensure_ascii=False, indent=2)}

{reference_section}

=== 출력 형식 ===
완전한 TSX 파일 내용만 출력하세요. 마크다운 블록이나 추가 설명은 포함하지 마세요.
"""

        messages = [
            {
                "role": "system",
                "content": "당신은 최고 수준의 React TypeScript 개발자입니다. Figma JSON 데이터를 정확히 분석해서 시각적으로 동일한 React 컴포넌트를 생성해주세요. styled-components를 사용하여 프로덕션 레벨의 코드를 작성하세요. Figma의 레이아웃, 색상, 타이포그래피, 간격 등 모든 시각적 요소를 정확히 반영해야 합니다.",
            },
            {"role": "user", "content": prompt},
        ]
        return await self.llm_service.generate_completion(messages)

    async def _find_similar_component_async(
        self,
        figma_document: Dict,
        guide_md_path: str = "./output/frontend/COMPONENTS_GUIDE.md",
    ) -> tuple[bool, dict | str]:
        """COMPONENTS_GUIDE.md를 기준으로 유사 컴포넌트를 LLM으로 판별 (비동기 버전)

        - FastAPI 등 이미 실행 중인 이벤트 루프에서 사용
        - 유사한 컴포넌트가 있으면 {index, name, reason} 반환
        - 없으면 {index: -1, name: (추정 새 이름), reason: "no similar one"}
        """
        try:
            guide_text = self._read_text_file(guide_md_path)
            guide_json = self._extract_guide_json(guide_text)

            components: Dict[str, Any] = (
                guide_json.get("component_description", {})
                if isinstance(guide_json, dict)
                else {}
            )
            if not isinstance(components, dict):
                return False, "COMPONENTS_GUIDE 구조가 올바르지 않습니다."

            component_catalog = [
                {
                    "name": name,
                    "index": (
                        int(meta.get("index"))
                        if isinstance(meta, dict) and "index" in meta
                        else None
                    ),
                    "purpose": (meta.get("purpose") if isinstance(meta, dict) else "")
                    or "",
                    "main_features": (
                        meta.get("main_features") if isinstance(meta, dict) else ""
                    )
                    or "",
                }
                for name, meta in components.items()
                if isinstance(meta, dict)
            ]

            # LLM 질의 실행 (이미 실행중인 이벤트 루프에서 대기)
            llm_result_text = await self._ask_llm_for_similarity(
                figma_document, component_catalog
            )

            parsed = self._extract_json_object(llm_result_text)
            if not isinstance(parsed, dict):
                return False, f"LLM 응답 파싱 실패: {llm_result_text[:200]}..."

            name = str(parsed.get("name", "")).strip()
            reason = str(parsed.get("reason", "")).strip()

            if (
                name in components
                and isinstance(components[name], dict)
                and "index" in components[name]
            ):
                index = int(components[name]["index"])  # 카탈로그의 실제 인덱스 사용
            else:
                index = -1
                if not name:
                    raw_name = (
                        str(figma_document.get("name", "component")).strip()
                        or "component"
                    )
                    name = self._slugify_component_name(raw_name)
                if not reason:
                    reason = "no similar one"

            result = {"index": index, "name": name, "reason": reason}
            print(f"🔎 Similar component decision: {result}")
            return True, result

        except Exception as e:
            return False, f"유사 컴포넌트 판별 실패: {str(e)}"

    async def _ask_llm_for_similarity(
        self, figma_document: Dict, component_catalog: list[dict]
    ) -> str:
        """LLM에게 카탈로그 중 유사 컴포넌트를 고르거나 새 컴포넌트로 판정하도록 요청"""
        try:
            system = (
                "당신은 숙련된 UI 컴포넌트 아키텍트입니다. "
                "주어진 Figma 컴포넌트 JSON의 의도와 상호작용/레이아웃 특징을 분석하여, "
                "아래 제공된 카탈로그 중 가장 유사한 단일 컴포넌트를 선택하세요. "
                "충분히 유사한 항목이 없다면 '새 컴포넌트'로 판정하세요."
            )

            instructions = (
                "출력 형식: 마크다운 없이 순수 JSON 객체만. 키는 index(숫자), name(문자열), reason(문자열).\n"
                "- 카탈로그에서 선택 시: name은 카탈로그의 키와 정확히 일치해야 함, index는 카탈로그의 index를 사용하지 않아도 되며 코드가 정규화함.\n"
                "- 새 컴포넌트 시: index는 -1 로 설정, name은 의도를 반영한 간결한 kebab-case 이름(예: ribbon-table), reason은 'no similar one' 포함.\n"
                "- 불필요한 텍스트, 코드펜스, 주석 금지."
            )

            user_prompt = {
                "figma_component_document": figma_document,
                "component_catalog": component_catalog,
            }

            messages = [
                {"role": "system", "content": system},
                {
                    "role": "user",
                    "content": json.dumps(user_prompt, ensure_ascii=False),
                },
                {"role": "user", "content": instructions},
            ]

            return await self.llm_service.generate_completion(messages)

        except Exception as e:
            print(f"❌ LLM 유사도 판단 실패: {e}")
            raise

    def _read_text_file(self, path: str) -> str:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def _extract_guide_json(self, md_text: str) -> Dict[str, Any]:
        """COMPONENTS_GUIDE.md 내부의 JSON 코드블록을 추출/파싱"""
        codeblock_match = re.search(r"```(?:json)?\s*([\s\S]*?)```", md_text)
        if not codeblock_match:
            # 코드블록이 없으면 전체를 JSON으로 시도
            return json.loads(md_text)
        code = codeblock_match.group(1)
        return json.loads(code)

    def _extract_json_object(self, text: str) -> Dict[str, Any] | str:
        """응답 텍스트에서 JSON 객체를 추출/파싱. 실패 시 원문 반환"""
        cleaned = text.strip()
        # 코드펜스 제거
        if cleaned.startswith("```"):
            lines = cleaned.split("\n")
            if lines and lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned = "\n".join(lines).strip()

        # 바로 파싱 시도
        try:
            return json.loads(cleaned)
        except Exception:
            pass

        # 첫 번째 중괄호 객체 추출
        brace_match = re.search(r"\{[\s\S]*\}", cleaned)
        if brace_match:
            candidate = brace_match.group(0)
            try:
                return json.loads(candidate)
            except Exception:
                return cleaned
        return cleaned

    def _slugify_component_name(self, name: str) -> str:
        slug = name.lower().strip()
        slug = re.sub(r"\s+", "-", slug)
        slug = re.sub(r"[^a-z0-9-]", "", slug)
        return slug or "custom-component"

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
            filename = f"{self.component_name.lower()}.tsx"
            file_path = os.path.join(output_dir, filename)

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
