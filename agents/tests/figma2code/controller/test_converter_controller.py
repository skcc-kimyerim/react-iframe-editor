from unittest.mock import patch

from app.figma2code.chat.controller.dto.chat_dto import ChatMessageResponseDTO
from fastapi.testclient import TestClient


class TestChatControllerE2E:
    async def test_chat_controller_e2e_with_mock(self, client: TestClient) -> None:
        # Given
        response_dto = ChatMessageResponseDTO(
            id="1234",
            chat_id="1234",
            content="Hello, world!",
        )

        # When
        with patch(
            "app.figma2code.chat.service.chat_service.ChatService.process_chat_message",
            return_value=response_dto,
        ):
            response = client.post(
                "/chat/completions/stream",
                json={"chat_id": "1234", "message": "Hello, world!"},
            )

        # Then
        assert response.status_code == 200
        assert response.json() == {
            "id": "1234",
            "chat_id": "1234",
            "content": "Hello, world!",
        }
