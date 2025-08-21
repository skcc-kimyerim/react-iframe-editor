from typing import AsyncGenerator, List

import pytest
from app.core.db.model.base import Base
from app.figma2code.chat.domain.chat import Chat
from app.figma2code.chat.domain.chat_message import ChatMessage
from app.figma2code.user.domain.user import User
from app.main import app
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


@pytest.fixture(scope="session")
def client() -> TestClient:
    return TestClient(app)


@pytest.fixture(scope="session")
def db_engine() -> AsyncEngine:
    engine = create_async_engine(
        "sqlite+aiosqlite:///test.db", connect_args={"check_same_thread": False}
    )
    return engine


@pytest.fixture(scope="function")  # 각 테스트 함수마다 새로운 DB 세션
async def session(db_engine: AsyncEngine) -> AsyncGenerator[AsyncSession, None]:
    # main.py의 Base와 User 모델을 사용하여 테이블 생성
    _models = [User, Chat, ChatMessage]

    SessionLocal = async_sessionmaker(bind=db_engine, expire_on_commit=False)

    async with db_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    session = SessionLocal()

    try:
        yield session
    finally:
        # 세션 명시적으로 닫기
        await session.close()

        # 테이블 내용 완전 삭제 (테스트 간 격리)
        async with db_engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)


class MockChatCompletionMessage:
    def __init__(self, content: str):
        self.content = content


class MockChatCompletionChoice:
    def __init__(self, message: MockChatCompletionMessage):
        self.message = message


class MockChatCompletion:
    def __init__(self, choices: List[MockChatCompletionChoice]):
        self.choices = choices
