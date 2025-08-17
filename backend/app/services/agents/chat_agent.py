import logging
import anthropic
from app.core.config import settings
from .image_utils import process_attachment_for_claude

logger = logging.getLogger("app.chat.workflow")


class ChatAgent:
    async def reply(self, user_input: str, model: str | None = None, attachments: list[dict] | None = None) -> str:
        api_key = settings.ANTHROPIC_API_KEY
        if not api_key:
            return "ANTHROPIC_API_KEY가 설정되지 않았습니다."

        try:
            client = anthropic.Anthropic(api_key=api_key)
            
            system_message = (
                "다음 사용자 요청에 대해 한국어로 명확하고 충분한 답변을 제공하세요. "
                "불필요한 사족은 줄이고, 필요한 경우 목록이나 간단한 코드/예시를 포함해 실용적으로 답하세요."
            )
            
            # 사용자 메시지 구성 (텍스트 + 이미지)
            user_content = []
            
            # 텍스트 메시지 추가
            if user_input.strip():
                user_content.append({
                    "type": "text",
                    "text": user_input
                })
            
            # 첨부 파일 처리 (이미지는 base64로, 기타는 텍스트로)
            if attachments:
                for attachment in attachments:
                    processed = await process_attachment_for_claude(attachment)
                    if processed:
                        user_content.append(processed)
            
            # 기본 텍스트가 없고 첨부만 있는 경우
            if not user_input.strip() and attachments:
                user_content.insert(0, {
                    "type": "text", 
                    "text": "첨부된 내용을 분석해주세요."
                })
            
            message = client.messages.create(
                model=model or "claude-sonnet-4-20250514",  # 기본값은 3.5, 프론트에서 4 지정 시 사용
                max_tokens=1000,
                system=system_message,
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
            
            return content.strip() or "요청을 확인했습니다. 관련 코드를 점검하고 필요한 수정을 백그라운드에서 진행할게요."
            
        except Exception as e:
            logger.exception("Claude API 요청 실패")
            return f"Claude API 요청 실패: {e}"

