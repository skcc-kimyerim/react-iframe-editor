from pydantic_settings import BaseSettings, SettingsConfigDict
from pathlib import Path
import logging
import sys
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


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

# .env 로드 우선순위: backend/.env → 프로젝트 루트/.env
_BACKEND_DIR = Path(__file__).resolve().parents[2]
_PROJECT_ROOT = _BACKEND_DIR.parent
load_dotenv(_BACKEND_DIR / ".env")
load_dotenv(_PROJECT_ROOT / ".env")

settings = Settings()

# Logging 설정
def setup_logging():
    """애플리케이션 전체 로깅 설정"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(sys.stdout),
        ]
    )
    
    # uvicorn 로거 설정
    uvicorn_logger = logging.getLogger("uvicorn")
    uvicorn_logger.setLevel(logging.INFO)
    
    # 애플리케이션 로거 생성
    app_logger = logging.getLogger("app")
    app_logger.setLevel(logging.INFO)
    
    return app_logger

def setup_middleware(app: FastAPI) -> None:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ALLOW_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

