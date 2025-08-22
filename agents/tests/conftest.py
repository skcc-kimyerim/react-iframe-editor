from typing import List

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from web.router import router


@pytest.fixture(scope="session")
def client() -> TestClient:
    # main.py는 DB 초기화(import 시 모델 누락)로 실패할 수 있으므로 라우터만 직접 마운트
    test_app = FastAPI()
    test_app.include_router(router)
    return TestClient(test_app)


class MockChatCompletionMessage:
    def __init__(self, content: str):
        self.content = content


class MockChatCompletionChoice:
    def __init__(self, message: MockChatCompletionMessage):
        self.message = message


class MockChatCompletion:
    def __init__(self, choices: List[MockChatCompletionChoice]):
        self.choices = choices
