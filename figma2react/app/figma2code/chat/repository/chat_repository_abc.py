from abc import abstractmethod

from core.bind.repository import Repository
from figma2code.chat.domain.chat import Chat


class ChatRepositoryABC(Repository):
    @abstractmethod
    async def create_chat(self, chat: Chat) -> Chat:
        pass

    @abstractmethod
    async def get_or_create_chat(self, chat: Chat) -> Chat:
        pass

    @abstractmethod
    async def get_chat(self, chat_id: str) -> Chat:
        pass
