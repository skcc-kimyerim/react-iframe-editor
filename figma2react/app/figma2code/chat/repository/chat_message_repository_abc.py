from abc import abstractmethod

from core.bind.repository import Repository
from figma2code.chat.domain.chat_message import ChatMessage


class ChatMessageRepositoryABC(Repository):
    @abstractmethod
    async def create_chat_message(self, chat_message: ChatMessage) -> ChatMessage:
        pass
