from core.db.connection import get_session
from fastapi import Depends
from figma2code.chat.domain.chat_message import ChatMessage
from figma2code.chat.repository.chat_message_repository_abc import (
    ChatMessageRepositoryABC,
)
from sqlalchemy.ext.asyncio import AsyncSession


class ChatMessageRepository(ChatMessageRepositoryABC):
    def __init__(self, session: AsyncSession):
        super().__init__(session)

    async def create_chat_message(self, chat_message: ChatMessage) -> ChatMessage:
        self.session.add(chat_message)

        await self.session.flush()
        await self.session.refresh(chat_message)

        return chat_message


def get_chat_message_repository(
    session: AsyncSession = Depends(get_session),
) -> ChatMessageRepository:
    return ChatMessageRepository(session)
