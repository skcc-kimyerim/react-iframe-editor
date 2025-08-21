from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

ENV_FILE = Path(__file__).resolve().parent.parent.parent / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # 앱 관련 설정
    APP_HOST: str = "0.0.0.0"
    APP_PORT: int = 8000

    # 데이터베이스 관련 설정
    DATABASE_URL: str = "sqlite+aiosqlite:///test.db"

    # 로깅 관련 설정 추가
    DATA_PATH: str = "./data"
    LOG_PATH: str = "/logs"
    ENVIRONMENT: str = "LOCAL"
    LOG_LEVEL: str = "DEBUG"
    APP_NAME: str = "genai-boilerplate"

    CMMN_API_URI: str = "https://cmmn-api.skcc.com"
    KEY_API_URL: str = "https://key-api.skcc.com"

    # LLM 관련 설정
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = ""
    OPENAI_MODEL: str = ""
    OPENAI_DEPLOYMENT: str = ""
    OPENAI_API_VERSION: str = ""

    # Figma 관련 설정 (figma2html에서 사용)
    FIGMA_API_TOKEN: str | None = None
    FIGMA_WORKER_COUNT: int = 4
    FIGMA_API_TIMEOUT: int = 30
    FIGMA_DOWNLOAD_TIMEOUT: int = 30

    # Azure OpenAI (AOAI) 설정
    AOAI_ENDPOINT: str = ""
    AOAI_API_KEY: str = ""
    AOAI_DEPLOY_GPT4O_MINI: str = ""
    AOAI_DEPLOY_GPT4O: str = ""
    AOAI_DEPLOY_EMBED_3_LARGE: str = ""
    AOAI_DEPLOY_EMBED_3_SMALL: str = ""
    AOAI_DEPLOY_EMBED_ADA: str = ""

    # OpenRouter / 기타 모델 설정
    O3_MINI_API_KEY: str = ""
    O3_MINI_ENDPOINT: str = ""
    O3_MINI_DEPLOYMENT_NAME: str = ""
    OPENROUTER_API_KEY: str = ""


settings = Settings()


def get_setting() -> Settings:
    return settings
