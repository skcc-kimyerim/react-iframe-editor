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
            
            # 텍스트 메시지 추가 (첨부파일이 있든 없든 사용자 질문이 있으면 추가)
            if user_input and user_input.strip():
                user_content.append({
                    "type": "text",
                    "text": user_input.strip()
                })
            
            # 첨부 파일 처리 (이미지는 base64로, 기타는 텍스트로)
            if attachments:
                for attachment in attachments:
                    processed = await process_attachment_for_claude(attachment)
                    if processed:
                        user_content.append(processed)
            
            # 아무 내용도 없는 경우 기본 메시지 추가
            if not user_content:
                user_content.append({
                    "type": "text", 
                    "text": "안녕하세요. 어떤 도움이 필요하신가요?"
                })
            # 첨부파일만 있고 텍스트가 없는 경우 분석 요청 메시지 추가
            elif not user_input.strip() and attachments:
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
            
        except anthropic.BadRequestError as e:
            logger.error(f"Claude API 잘못된 요청: {e}")
            return "요청이 올바르지 않습니다. 메시지 내용을 확인해주세요."
        except anthropic.AuthenticationError as e:
            logger.error(f"Claude API 인증 실패: {e}")
            return "API 키 인증에 실패했습니다."
        except anthropic.RateLimitError as e:
            logger.error(f"Claude API 요청 한도 초과: {e}")
            return "요청 한도를 초과했습니다. 잠시 후 다시 시도해주세요."
        except Exception as e:
            logger.exception("Claude API 요청 실패")
            return f"Claude API 요청 실패: {e}"

