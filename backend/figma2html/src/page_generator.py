import asyncio
import json
import os
import re
from typing import List, Tuple

from colorama import init

from .react_generator import ReactComponentGenerator

init()

COMPONENTS_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../frontend/src/test-components")
)
PAGE_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "../../../frontend/src/pages")
)


def make_filename(raw_name: str) -> str:
    """
    Figma 페이지 이름을 기반으로 PascalCase + 'Page'
    예: 'main screen' -> 'MainScreenPage.tsx'
    """
    # 영문/숫자만 추출하여 PascalCase 변환
    words = re.findall(r"[A-Za-z0-9]+", raw_name)
    pascal = "".join(w.capitalize() for w in words) or "Page"
    base = pascal + "Page"
    return f"{base}.tsx"


class PageGenerator:
    def __init__(self, components_dir: str = None):
        self.react_generator = ReactComponentGenerator()
        # components_dir이 지정되면 사용, 아니면 기본 경로 사용
        self.components_dir = components_dir or None

    def get_test_components_list(self) -> List[str]:
        files = os.listdir(self.components_dir)
        return [f[:-4] for f in files if f.endswith(".tsx")]

    def generate_layout_with_llm(
        self, html_code: str, css_code: str, output: str
    ) -> Tuple[bool, str]:
        """
        html_generator의 HTML/CSS 결과를 LLM 프롬프트에 포함해 TSX 생성
        test-components/에 있는 모든 컴포넌트의 props/type/interface 정의를 프롬프트에 포함
        """
        # components 디렉토리가 존재하는지 확인
        if not self.components_dir or not os.path.exists(self.components_dir):
            # 컴포넌트 없이 HTML/CSS만으로 페이지 생성
            component_list_str = ""
            component_docs = ""
            mapping_rules = ""
            usage_examples = ""
        else:
            # components 디렉토리의 컴포넌트 목록 (확장자 제외)
            component_files = [
                f for f in os.listdir(self.components_dir) if f.endswith(".tsx")
            ]
            component_list = [f[:-4] for f in component_files]
            component_list_str = ", ".join(component_list)

            # 각 컴포넌트의 props/type/interface 정의 추출
            docs_blocks = []
            for filename in component_files:
                path = os.path.join(self.components_dir, filename)
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        code = f.read()

                    # 모든 interface와 type 정의 추출
                    interfaces = re.findall(
                        r"(interface [A-Za-z0-9_]+(?:Props)?\s*\{[\s\S]*?\n\})", code
                    )
                    types = re.findall(
                        r"(type [A-Za-z0-9_]+(?:Props)?\s*=\s*\{[\s\S]*?\n\})", code
                    )

                    # Props가 아닌 일반 interface/type도 포함 (예: TabItem)
                    all_definitions = interfaces + types

                    if all_definitions:
                        # 모든 정의를 하나의 블록으로 합치기
                        full_docs = "\n".join(all_definitions)
                        docs_blocks.append(f"[{filename}]\n{full_docs}\n")
                    else:
                        # function 컴포넌트 signature
                        match = re.search(r"(function [A-Za-z0-9_]+\([\s\S]+?\))", code)
                        if match:
                            docs_blocks.append(f"[{filename}]\n{match.group(1)}\n")
                        else:
                            # 파일 앞부분 최대 40줄만
                            lines = code.splitlines()
                            docs_blocks.append(
                                f"[{filename}]\n" + "\n".join(lines[:40]) + "\n"
                            )
                except Exception as e:
                    docs_blocks.append(f"[{filename}]\n(문서 추출 실패: {e})\n")

            component_docs = "[components props/type docs]\n" + "\n".join(docs_blocks)

            # 컴포넌트 디렉토리 이름 추출 (경로의 마지막 부분)
            components_dir_name = (
                os.path.basename(self.components_dir)
                if self.components_dir
                else "components"
            )

            mapping_rules = (
                "아래 HTML 구조에서 class명, 텍스트, 계층, placeholder, label 등을 참고해서 "
                f"{components_dir_name}/에 이미 존재하는 컴포넌트로 적극적으로 매핑해줘.\n"
                "매핑 규칙 예시:\n"
                "- class에 'button'이 포함되어 있고, 내부 텍스트가 'confirm', 'Send message' 등인 경우: Button 컴포넌트로 대체\n"
                "- class에 'field', 'input'이 포함되어 있고, 내부에 'Email', 'Password' 등 텍스트가 있으면: Input 컴포넌트로 대체\n"
                "- class에 'textarea'가 포함되어 있고, 내부에 'Type your message here' 등 placeholder가 있으면: Textarea 컴포넌트로 대체\n"
                "이외에도, label/placeholder/텍스트/계층 정보를 적극적으로 활용해서 컴포넌트로 매핑해줘.\n"
                f"import는 반드시 {components_dir_name}/에서 하고, 나머지는 styled-components로 만들어도 돼.\n"
            )

            usage_examples = (
                "각 컴포넌트는 placeholder, value, onChange, type 등 props를 적극적으로 활용해줘.\n"
                "중요: onChange는 (value: string) => void 타입이므로 e.target.value 대신 value를 직접 사용해줘.\n"
                "Button은 onClick 등 이벤트 핸들러도 추가해줘.\n"
                "필요하다면 useState, useCallback 등 React 훅을 사용해서 state와 이벤트 핸들러도 구현해.\n"
                "예시:\n"
                '  <Input placeholder="Email" value={email} onChange={(e) => setEmail(e.target.value)} type="email" />\n'
                "  <Button onClick={handleClick}>confirm</Button>\n"
                '  <Textarea placeholder="Type your message here" value={message} onChange={(e) => setMessage(e.target.value)} />\n'
                "이 코드는 실제로 동작하는 React 페이지여야 하며, 단순한 시각적 mockup이 아니어야 해.\n"
            )

        # 컴포넌트가 있는 경우와 없는 경우에 따라 다른 프롬프트 생성
        if component_list_str:
            prompt = (
                "아래는 Figma에서 추출한 HTML/CSS입니다.\n"
                f"아래 컴포넌트들은 {components_dir_name}/에 이미 존재하니, 반드시 import해서 적극 활용해줘: [{component_list_str}]\n"
                f"import 할 때는 반드시 각각 개별적으로 import 해야 합니다:\n"
                f"예시: import NavigationMenu from '../{components_dir_name}/NavigationMenu';\n"
                f"절대 import {{ ... }} from '{components_dir_name}' 형태로 하지 마세요.\n"
                f"{component_docs}"
                f"{mapping_rules}"
                f"{usage_examples}"
                "실제 Figma와 동일한 TSX(React) 페이지를 완성해줘.\n"
                "중요: ```tsx 같은 마크다운 코드블록을 절대 포함하지 마세요. 순수한 TSX 코드만 출력하세요.\n"
                "중요: 무조건 figma와 동일하게 만들어지는게 중요합니다. 무조건 디자인 따라서 만들어야 합니다.\n"
                "파일명은 페이지 이름을 기반으로 생성해줘.\n"
                f"HTML:\n{html_code}\n"
                f"CSS:\n{css_code}\n"
            )
        else:
            # 컴포넌트 없이 HTML/CSS만으로 페이지 생성
            prompt = (
                "아래는 Figma에서 추출한 HTML/CSS입니다.\n"
                "이 HTML/CSS를 바탕으로 완전한 React TypeScript 페이지를 생성해주세요.\n"
                "중요 사항:\n"
                "- TypeScript + styled-components 사용\n"
                "- HTML 구조를 정확히 React 컴포넌트로 변환\n"
                "- CSS 스타일을 styled-components로 변환\n"
                "- useState, useCallback 등 필요한 React 훅 사용\n"
                "- 실제로 동작하는 페이지로 만들어주세요\n"
                "- ```tsx 같은 마크다운 코드블록을 절대 포함하지 마세요. 순수한 TSX 코드만 출력하세요.\n"
                "- 무조건 figma와 동일하게 만들어지는게 중요합니다. 무조건 디자인 따라서 만들어야 합니다.\n"
                f"HTML:\n{html_code}\n"
                f"CSS:\n{css_code}\n"
            )
        try:
            tsx_code = asyncio.run(
                self.react_generator._generate_react_from_html_css_with_prompt(prompt)
            )
            return True, tsx_code
        except Exception as e:
            return False, str(e)

    def generate_component_with_llm(self, component_json: dict) -> Tuple[bool, str]:
        """
        하나의 섹션/프레임 JSON을 LLM에 전달해 컴포넌트 TSX 생성
        """
        component_name = re.sub(
            r"[^A-Za-z0-9]", "", component_json.get("name", "Component")
        )
        prompt = f"""
파일명: {component_name}.tsx

아래는 Figma에서 추출한 섹션 JSON입니다:
{json.dumps(component_json, ensure_ascii=False, indent=2)}

- TypeScript + styled-components 사용
- 이 파일은 `export default function {component_name}()` 형태의 완전한 TSX만 출력
- 설명, 마크다운 금지
"""
        try:
            tsx_code = asyncio.run(
                self.react_generator._generate_react_from_figma_json_with_prompt(prompt)
            )
            return True, tsx_code
        except Exception as e:
            return False, str(e)
