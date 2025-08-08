from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path


class Settings(BaseSettings):
    PORT: int = 3001
    REACT_DEV_PORT: int = 3002
    # backend/app/core/config.py → backend 디렉토리로 올라가서 동적 프로젝트 경로 지정
    REACT_PROJECT_PATH: Path = Path(__file__).resolve().parents[2] / "dynamic-react-app"
    OPENROUTER_API_KEY: str | None = None
    CORS_ALLOW_ORIGINS: list[str] = ["*"]

    # pydantic-settings v2 구성: .env 로드 및 불필요한 키 무시
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
        extra="ignore",
    )


settings = Settings()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def setup_middleware(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOW_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

