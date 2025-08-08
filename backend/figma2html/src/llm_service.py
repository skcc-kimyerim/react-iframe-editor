"""
LLM Service Module
OpenRouter와 Azure OpenAI를 통합 관리하는 서비스
"""

import os
from typing import Optional

import openai
from dotenv import load_dotenv


class LLMService:
    """LLM 서비스 통합 관리 클래스"""

    def __init__(self):
        # 환경변수 로드 (여러 경로 시도)
        load_dotenv()
        load_dotenv(dotenv_path="../.env")
        load_dotenv(dotenv_path="../../.env")
        load_dotenv(dotenv_path="../../../.env")

        # 환경변수 확인
        self.is_router = os.getenv("IS_ROUTER")
        self.router_api_key = os.getenv("OPENROUTER_API_KEY")
        self.azure_api_key = os.getenv("AOAI_API_KEY")
        self.azure_endpoint = os.getenv("AOAI_ENDPOINT")
        self.azure_deployment = os.getenv("AOAI_DEPLOY_GPT4O")

        # LLM 클라이언트 초기화
        self.client, self.model_name = self._initialize_llm_client()

    def _initialize_llm_client(self):
        """LLM 클라이언트 초기화"""
        if self.is_router and self.is_router.upper() == "TRUE":
            # OpenRouter 사용
            if not self.router_api_key:
                raise ValueError("OPENROUTER_API_KEY 환경변수가 설정되지 않았습니다.")

            client = openai.AsyncOpenAI(
                api_key=self.router_api_key,
                base_url="https://openrouter.ai/api/v1",
                default_headers={
                    "HTTP-Referer": "https://github.com/figma-to-react",
                    "X-Title": "Figma to React Converter",
                },
            )
            # model_name = "anthropic/claude-sonnet-4"  # Claude 사용시
            model_name = "qwen/qwen3-coder:free"  # Qwen 사용시
            return client, model_name
        else:
            # Azure OpenAI 사용
            if not self.azure_api_key:
                raise ValueError("AOAI_API_KEY 환경변수가 설정되지 않았습니다.")
            if not self.azure_endpoint:
                raise ValueError("AOAI_ENDPOINT 환경변수가 설정되지 않았습니다.")
            if not self.azure_deployment:
                raise ValueError("AOAI_DEPLOY_GPT4O 환경변수가 설정되지 않았습니다.")

            client = openai.AsyncAzureOpenAI(
                azure_endpoint=self.azure_endpoint,
                api_key=self.azure_api_key,
                api_version="2024-02-01",
            )
            return client, self.azure_deployment

    async def generate_completion(
        self, messages: list, max_tokens: int = 4000, temperature: float = 0.1
    ) -> str:
        """LLM 완성 생성"""
        try:
            response = await self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                max_tokens=max_tokens,
                temperature=temperature,
            )
            return response.choices[0].message.content.strip()
        except Exception as e:
            print(f"❌ LLM 코드 생성 실패: {e}")
            raise

    def get_model_info(self) -> dict:
        """현재 사용 중인 모델 정보 반환"""
        return {
            "provider": "OpenRouter"
            if self.is_router and self.is_router.upper() == "TRUE"
            else "Azure OpenAI",
            "model": self.model_name,
            "is_router": bool(self.is_router and self.is_router.upper() == "TRUE"),
        }


# 싱글톤 인스턴스
_llm_service: Optional[LLMService] = None


def get_llm_service() -> LLMService:
    """LLM 서비스 싱글톤 인스턴스 반환"""
    global _llm_service
    if _llm_service is None:
        _llm_service = LLMService()
    return _llm_service
