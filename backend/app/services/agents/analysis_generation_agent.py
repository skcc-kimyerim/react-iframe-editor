from __future__ import annotations

import logging
from typing import Any, Dict, Optional

import httpx
from app.core.config import settings

logger = logging.getLogger("app.chat.workflow")


class AnalysisGenerationAgent:
    async def generate_analysis(
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

        system = (
            "당신은 React/TypeScript 코드 분석가입니다. 사용자의 질문과 선택된 파일, "
            "그리고 프로젝트 컨텍스트를 바탕으로 한국어로 명확한 분석 리포트를 작성하세요.\n"
            "- 요약\n- 파일 개요(역할, 주요 export/컴포넌트)\n- 중요한 상태/함수/로직\n"
            "- 의존성 및 사용처(연관 파일/컴포넌트)\n- 잠재 이슈 및 개선 제안\n"
            "코드 수정본이나 FILEPATH 지시문, 코드 펜스는 포함하지 마세요. 필요 시 짧은 코드 조각만 인라인로 인용하세요."
        )
        if selected_file and file_content is not None:
            system += f"""

선택된 파일: {selected_file}
현재 파일 내용:
{file_content}
"""
        if enhanced_context:
            system += f"""

프로젝트 컨텍스트:
{enhanced_context}
"""
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
                system += """

첨부 자료(URL):
""" + "\n".join(lines)

        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": question or "해당 파일을 분석해줘"},
        ]

        payload = {"model": model, "messages": messages, "stream": False, "temperature": 0.2}
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
            "HTTP-Referer": f"http://localhost:{settings.PORT}",
            "X-Title": "React Iframe Editor - Analysis",
        }

        try:
            async with httpx.AsyncClient(timeout=120) as client:
                r = await client.post("https://openrouter.ai/api/v1/chat/completions", headers=headers, json=payload)
                if r.status_code != 200:
                    return {"success": False, "message": f"API error: {r.text}"}
                data = r.json()
                content = data.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
                return {"success": True, "content": content.strip()}
        except Exception as e:
            logger.exception("Analysis generation failed")
            return {"success": False, "message": str(e)}

