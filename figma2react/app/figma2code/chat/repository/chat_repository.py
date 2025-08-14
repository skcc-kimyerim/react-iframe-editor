from core.db.connection import get_session
from fastapi import Depends
from figma2code.chat.domain.chat import Chat
from figma2code.chat.repository.chat_repository_abc import ChatRepositoryABC
from sqlalchemy.ext.asyncio import AsyncSession


class ChatRepository(ChatRepositoryABC):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def create_chat(self, chat: Chat) -> Chat:
        self.session.add(chat)

        await self.session.flush()
        await self.session.refresh(chat)

        return chat

    async def get_chat(self, chat_id: str) -> Chat:
        return await self.session.get(Chat, chat_id)

    async def get_or_create_chat(self, chat: Chat) -> Chat:
        existing_chat = await self.get_chat(chat.id)
        if existing_chat:
            return existing_chat
        return await self.create_chat(chat)


def get_chat_repository(
    session: AsyncSession = Depends(get_session),
) -> ChatRepository:
    return ChatRepository(session)
