from __future__ import annotations

import logging
from typing import Any, Dict, Optional
import anthropic
from app.core.config import settings
from .image_utils import process_attachment_for_claude

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
        api_key = settings.ANTHROPIC_API_KEY
        if not api_key:
            return {"success": False, "message": "ANTHROPIC_API_KEY not configured"}

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

        try:
            client = anthropic.Anthropic(api_key=api_key)
            
            # 사용자 메시지 구성
            user_content = []
            
            # 질문 텍스트 추가
            user_content.append({
                "type": "text",
                "text": question or "해당 파일을 분석해줘"
            })
            
            # 첨부 파일 처리
            if attachments:
                for attachment in attachments:
                    processed = await process_attachment_for_claude(attachment)
                    if processed:
                        user_content.append(processed)

            message = client.messages.create(
                model=model or "claude-sonnet-4-20250514",
                max_tokens=2000,
                system=system,
                messages=[{
                    "role": "user",
                    "content": user_content
                }]
            )
            
            # 응답 텍스트 추출
            content = ""
            for block in message.content:
                if block.type == "text":
                    content += block.text
            
            return {"success": True, "content": content.strip()}
            
        except Exception as e:
            logger.exception("Analysis generation failed")
            return {"success": False, "message": str(e)}

