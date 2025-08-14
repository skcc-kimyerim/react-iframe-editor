from __future__ import annotations

import re
from typing import Any, Dict, Optional

import httpx
from app.core.config import settings
from .utils import _to_pascal_case


class CodeGenerationAgent:
    async def propose_changes(
        self,
        model: str,
        question: str,
        selected_file: Optional[str],
        file_content: Optional[str],
        enhanced_context: Optional[str],
        attachments: Optional[list[dict]] = None,
    ) -> Dict[str, Any]:
        api_key = settings.OPENROUTER_API_KEY
        if not api_key:
            return {"success": False, "message": "OPENROUTER_API_KEY not configured"}

        system = "당신은 React/TypeScript 코드 전문가입니다."
        if selected_file and file_content is not None:
            system += f"""
        현재 선택된 파일: {selected_file}
        현재 파일 내용:{file_content}
"""
        if enhanced_context:
            system += f"""

프로젝트 컨텍스트:
{enhanced_context}

위 컨텍스트를 참고하여 관련 파일 간의 관계, 코드 스타일, 폴더 구조를 고려해서 답변하세요."""
        if attachments:
            lines = []
            for a in attachments:
                url = a.get("url")
                if not url:
                    continue
                name = a.get("name") or url.split("/")[-1]
                mime = a.get("mime") or ""
                lines.append(f"- {name} ({mime}): {url}")
            if lines:
                system += "\n\n첨부 자료(URL):\n" + "\n".join(lines)

        system += """
사용자의 요청에 따라 코드를 수정해야 하는 경우:
1) 먼저 수정 내용에 대한 간단한 설명
2) 수정된 전체 코드를 하나의 코드 블록(```typescript/```javascript/```tsx/```jsx)에 포함
3) 새 파일 생성 시 코드 블록 바로 위에 'FILEPATH: client/경로/파일명' 한 줄을 정확히 추가
   - 코드 펜스 헤더에 path=..., file=..., filename=..., title=... 도 허용 (예: ```tsx title=client/pages/Home.tsx)
   - 기존 파일 수정 시 FILEPATH 생략
설명은 간단하고 명확하게.

[중요: 새 파일 생성 위치 규칙]
- 새 페이지 파일은 반드시 client/pages/ 아래에 생성하세요.
- 새로 생성된 페이지는 반드시 App.tsx에 추가되어야 합니다.
- 새 컴포넌트 파일은 반드시 client/components/ui/ 아래에 생성하세요.
- 다른 위치에 새 파일을 만들지 마세요.

[파일명 규칙]
- 페이지 파일명은 반드시 PascalCase를 사용하세요 (예: AboutUs.tsx).
"""

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": question},
        ]

        payload = {
            "model": model,
            "messages": messages,
            "stream": False,
        }
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": f"http://localhost:{settings.PORT}",
            "X-Title": "React Iframe Editor - Agents",
        }

        async with httpx.AsyncClient(timeout=120) as client:
            r = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
            if r.status_code != 200:
                return {"success": False, "message": f"API error: {r.text}"}

            data = r.json()
            content = data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""

        file_path = None
        header_path_match = re.search(
            r'```(?:typescript|javascript|tsx|jsx)[^\n]*?(?:path|file(?:name)?|title)\s*[:=]\s*([^\s\n`]+)',
            content,
            re.IGNORECASE,
        )
        if header_path_match:
            file_path = header_path_match.group(1).strip().strip('"').strip("'")

        if not file_path:
            directive_match = re.search(r'(?im)^\s*(?:FILEPATH|FILE|FILENAME|PATH)\s*[:=]\s*(.+)$', content)
            if directive_match:
                file_path = directive_match.group(1).strip()

        if file_path:
            normalized_path = file_path.strip()
            if normalized_path.startswith("./"):
                normalized_path = normalized_path[2:]
            normalized_path = normalized_path.lstrip("/")
            if normalized_path.startswith("src/client/"):
                normalized_path = normalized_path[len("src/"):]
            elif normalized_path.startswith("src/"):
                normalized_path = "client/" + normalized_path[len("src/"):]
            if normalized_path.startswith("pages/"):
                normalized_path = "client/pages/" + normalized_path[len("pages/"):]
            if normalized_path.startswith("components/") and not normalized_path.startswith("components/ui/"):
                normalized_path = "client/components/ui/" + normalized_path[len("components/"):]

            if normalized_path.startswith("client/pages/"):
                parts = normalized_path.split("/")
                filename = parts[-1]
                if "." in filename:
                    base, ext = filename.rsplit(".", 1)
                    pascal = _to_pascal_case(base)
                    if base != pascal:
                        parts[-1] = f"{pascal}.{ext}"
                        normalized_path = "/".join(parts)
                else:
                    pascal = _to_pascal_case(filename)
                    if filename != pascal:
                        parts[-1] = pascal
                        normalized_path = "/".join(parts)
            file_path = normalized_path

        code_blocks = re.findall(r'```(?:typescript|javascript|tsx|jsx)\n(.*?)\n```', content, re.DOTALL)
        updated_content = code_blocks[0].strip() if code_blocks else None

        display = content
        if code_blocks:
            display = re.sub(r'```(?:typescript|javascript|tsx|jsx)\n.*?\n```', '', display, flags=re.DOTALL)
            display = re.sub(r'(?im)^\s*(?:FILEPATH|FILE|FILENAME|PATH)\s*[:=].+$', '', display)
            display = display.strip()
            if len(display) < 10:
                display = "코드 수정안을 생성했습니다. 백그라운드에서 적용 중입니다."

        return {
            "success": True,
            "display": display,
            "file_path": file_path,
            "updated_content": updated_content,
        }

