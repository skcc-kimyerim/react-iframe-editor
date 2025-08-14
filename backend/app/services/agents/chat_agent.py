import logging
import httpx
from app.core.config import settings

logger = logging.getLogger("app.chat.workflow")


class ChatAgent:
    async def reply(self, user_input: str, model: str | None = None, attachments: list[dict] | None = None) -> str:
        api_key = settings.OPENROUTER_API_KEY
        if not api_key:
            return "OPENROUTER_API_KEY가 없습니다."

        try:
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}",
                "HTTP-Referer": f"http://localhost:{settings.PORT}",
                "X-Title": "React Iframe Editor - Quick Reply",
            }
            system = (
                "다음 사용자 요청에 대해 한국어로 명확하고 충분한 답변을 제공하세요. "
                "불필요한 사족은 줄이고, 필요한 경우 목록이나 간단한 코드/예시를 포함해 실용적으로 답하세요."
            )
            user_content = user_input
            # 간단한 멀티모달: 이미지/파일 URL을 텍스트로 프롬프트에 추가
            # OpenRouter의 많은 모델이 이미지 배열을 직접 지원하지만, 통일성을 위해 URL/설명 텍스트로 주입
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
                    user_content += "\n\n[첨부]\n" + "\n".join(lines)

            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": user_content},
            ]
            payload = {
                "model": model or "qwen/qwen3-coder",
                "messages": messages,
                "stream": False,
                "temperature": 0.1,
            }

            async with httpx.AsyncClient(timeout=60) as client:
                r = await client.post(
                    "https://openrouter.ai/api/v1/chat/completions",
                    headers=headers,
                    json=payload,
                )
                if r.status_code != 200:
                    logger.warning("Quick reply OpenRouter error: %s", r.text)
                    return f"OpenRouter 요청 실패: {r.text}"

                data = r.json()
                content = (
                    data.get("choices", [{}])[0]
                    .get("message", {})
                    .get("content", "")
                    .strip()
                )
                return content or "요청을 확인했습니다. 관련 코드를 점검하고 필요한 수정을 백그라운드에서 진행할게요."
        except Exception as e:
            logger.exception("Quick reply generation failed")
            return f"OpenRouter 요청 실패: {e}"

