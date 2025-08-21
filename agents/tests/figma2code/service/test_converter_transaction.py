from unittest.mock import patch

import pytest
from app.core.db.database_transaction import transactional
from app.figma2code.chat.controller.dto.chat_dto import ChatMessageRequestDTO
from app.figma2code.chat.domain.chat import Chat
from app.figma2code.chat.domain.chat_message import ChatMessage
from app.figma2code.chat.repository.chat_message_repository import ChatMessageRepository
from app.figma2code.chat.repository.chat_repository import ChatRepository
from app.figma2code.chat.service.chat_service import ChatService
from app.figma2code.user.domain.user import User
from conftest import (
    MockChatCompletion,
    MockChatCompletionChoice,
    MockChatCompletionMessage,
)
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker


class TestChatTransactionSuccess:
    """성공적인 트랜잭션 테스트"""

    async def test_successful_chat_creation_commits_all_data(
        self, session: AsyncSession, db_engine: AsyncEngine
    ) -> None:
        """정상적인 채팅 생성시 chat과 chat_message가 모두 커밋되는지 테스트"""
        # Given: 테스트용 사용자 생성
        user = User(
            user_id="test-user-123",
            username="testuser",
            email="testuser@test.com",
            profile="test profile",
        )
        session.add(user)
        await session.commit()

        chat_service = ChatService(
            chat_repository=ChatRepository(session),
            chat_message_repository=ChatMessageRepository(session),
        )

        # When: ChatService로 채팅 처리
        command = ChatMessageRequestDTO(
            chat_id="test-chat-123",
            user_id="test-user-123",
            message="안녕하세요 테스트입니다",
        )

        # Mock ChatCompletion
        with patch("core.ai.azure_llm.AzureLLM.generate_text") as mock_generate_text:
            mock_generate_text.return_value = MockChatCompletion(
                choices=[
                    MockChatCompletionChoice(
                        message=MockChatCompletionMessage(
                            content="안녕하세요 테스트입니다"
                        )
                    )
                ]
            )
            result = await chat_service.process_chat_message(command)

        # Then: 반환 결과 검증
        assert result.chat_id == "test-chat-123"

        # Then: 데이터베이스에 실제로 저장되었는지 검증
        # 새로운 세션에서 조회해서 트랜잭션 커밋 여부 확인
        new_session = async_sessionmaker(
            autocommit=False, autoflush=False, bind=db_engine
        )
        new_session = new_session()

        saved_chat = await new_session.execute(
            select(Chat).where(Chat.id == "test-chat-123").limit(1)
        )
        saved_chat = saved_chat.scalars().first()
        assert saved_chat is not None
        assert saved_chat.user_id == "test-user-123"

        saved_messages = await new_session.execute(
            select(ChatMessage).where(ChatMessage.chat_id == "test-chat-123")
        )
        saved_messages = saved_messages.scalars().all()
        assert len(saved_messages) == 1
        assert saved_messages[0].role == "user"
        assert saved_messages[0].type == "text"

        await new_session.rollback()
        await new_session.close()

    async def test_existing_chat_adds_new_message(
        self, session: AsyncSession, db_engine: AsyncEngine
    ) -> None:
        """기존 채팅에 새 메시지 추가시 정상 동작 테스트"""
        # Given: 기존 사용자와 채팅 생성
        user = User(
            user_id="test-user-456",
            username="testuser2",
            email="testuser2@test.com",
            profile="test profile",
        )
        existing_chat = Chat(
            id="existing-chat-456", user_id="test-user-456", title="기존 채팅"
        )
        session.add(user)
        session.add(existing_chat)
        await session.commit()

        # When: 기존 채팅에 새 메시지 추가
        chat_service = ChatService(
            chat_repository=ChatRepository(session),
            chat_message_repository=ChatMessageRepository(session),
        )

        command = ChatMessageRequestDTO(
            chat_id="existing-chat-456",
            user_id="test-user-456",
            message="새로운 메시지입니다",
        )

        # Mock ChatCompletion
        with patch("core.ai.azure_llm.AzureLLM.generate_text") as mock_generate_text:
            mock_generate_text.return_value = MockChatCompletion(
                choices=[
                    MockChatCompletionChoice(
                        message=MockChatCompletionMessage(
                            content="안녕하세요 테스트입니다"
                        )
                    )
                ]
            )
            await chat_service.process_chat_message(command)

        # 새로운 세션에서 조회
        new_session = async_sessionmaker(
            autocommit=False, autoflush=False, bind=db_engine
        )
        new_session = new_session()

        # Then: 새 메시지가 추가되었는지 확인
        saved_messages = await new_session.execute(
            select(ChatMessage).where(ChatMessage.chat_id == "existing-chat-456")
        )
        saved_messages = saved_messages.scalars().all()
        assert len(saved_messages) == 1

        await new_session.rollback()
        await new_session.close()


class TestChatTransactionRollback:
    """트랜잭션 롤백 테스트"""

    async def test_exception_during_chat_message_creation_rolls_back_all_changes(
        self, session: AsyncSession
    ) -> None:
        """채팅 메시지 생성 중 예외 발생시 모든 변경사항이 롤백되는지 테스트"""
        # Given: 테스트용 사용자 생성
        user = User(
            user_id="test-user-rollback",
            username="rollback-user",
            email="rollback-user@test.com",
            profile="rollback-profile",
        )
        session.add(user)
        await session.commit()

        # Given: ChatMessageRepository.create_chat_message에서 예외 발생하도록 Mock
        chat_service = ChatService(
            chat_repository=ChatRepository(session),
            chat_message_repository=ChatMessageRepository(session),
        )

        with (
            patch("core.ai.azure_llm.AzureLLM.generate_text"),
            patch(
                "chat.repository.chat_message_repository.ChatMessageRepository.create_chat_message"
            ) as mock_create_message,
        ):
            # 채팅 메시지 생성시 예외 발생
            mock_create_message.side_effect = Exception("메시지 생성 실패!")

            command = ChatMessageRequestDTO(
                chat_id="rollback-test-chat",
                user_id="test-user-rollback",
                message="롤백 테스트 메시지",
            )

            # When: 예외가 발생해야 함
            with pytest.raises(Exception, match="메시지 생성 실패!"):
                await chat_service.process_chat_message(command)

        # Then: 채팅도 생성되지 않았는지 확인 (전체 롤백)
        saved_chat = await session.execute(
            select(Chat).where(Chat.id == "rollback-test-chat").limit(1)
        )
        saved_chat = saved_chat.scalars().first()
        assert saved_chat is None

        saved_messages = await session.execute(
            select(ChatMessage).where(ChatMessage.chat_id == "rollback-test-chat")
        )
        saved_messages = saved_messages.scalars().all()
        assert len(saved_messages) == 0

    # sqlite 에서는 외래키 제약조건 위반시 롤백되지 않음
    # def test_database_constraint_violation_rolls_back_transaction(
    #     self, session: Session
    # ) -> None:
    #     """데이터베이스 제약조건 위반시 롤백되는지 테스트"""
    #     # Given: 존재하지 않는 사용자 ID로 채팅 생성 시도
    #     chat_service = ChatService(session=session)
    #     command = ChatCommand(
    #         chat_id="constraint-test-chat",
    #         user_id="nonexistent-user",
    #         message="제약조건 테스트",
    #     )

    #     # When & Then: 외래키 제약조건 위반으로 예외 발생해야 함
    #     with pytest.raises(Exception):  # SQLAlchemy IntegrityError 등
    #         chat_service.process_chat(command)

    #     # Then: 아무것도 저장되지 않았는지 확인
    #     saved_chat = (
    #         session.query(Chat).filter(Chat.id == "constraint-test-chat").first()
    #     )
    #     assert saved_chat is None

    #     saved_messages = (
    #         session.query(ChatMessage)
    #         .filter(ChatMessage.chat_id == "constraint-test-chat")
    #         .all()
    #     )
    #     assert len(saved_messages) == 0


class FailingChatService(ChatService):
    """테스트용: 중간에 실패하는 ChatService"""

    @transactional
    async def process_chat_message(self, command: ChatMessageRequestDTO) -> None:
        # 채팅은 생성되지만 메시지 생성 전에 실패
        await self.chat_repository.get_or_create_chat(
            Chat(
                id=command.chat_id,
                user_id=command.user_id,
                title=command.message,
            )
        )

        # 여기서 의도적으로 실패
        raise Exception("의도적인 실패!")


class TestChatTransactionIntegration:
    """통합 트랜잭션 테스트"""

    async def test_custom_failing_service_rolls_back_properly(
        self, session: AsyncSession
    ) -> None:
        """커스텀 실패 서비스를 통한 롤백 테스트"""
        # Given: 테스트용 사용자
        user = User(
            user_id="integration-user",
            username="integration-user",
            email="integration-user@test.com",
            profile="integration-profile",
        )
        session.add(user)
        await session.commit()

        # When: 실패하는 ChatService 사용
        failing_service = FailingChatService(
            chat_repository=ChatRepository(session),
            chat_message_repository=ChatMessageRepository(session),
        )
        command = ChatMessageRequestDTO(
            chat_id="integration-test-chat",
            user_id="integration-user",
            message="통합 테스트 메시지",
        )

        with pytest.raises(Exception, match="의도적인 실패!"):
            await failing_service.process_chat_message(command)

        # Then: 채팅도 롤백되었는지 확인
        saved_chat = await session.execute(
            select(Chat).where(Chat.id == "integration-test-chat").limit(1)
        )
        saved_chat = saved_chat.scalars().first()
        assert saved_chat is None

    async def test_multiple_operations_in_single_transaction(
        self, session: AsyncSession
    ) -> None:
        """단일 트랜잭션에서 여러 작업이 모두 커밋되는지 테스트"""
        # Given: 테스트용 사용자
        user = User(
            user_id="multi-op-user",
            username="multi-op-user",
            email="multi-op-user@test.com",
            profile="multi-op-profile",
        )
        session.add(user)
        await session.commit()

        # When: 여러 채팅 작업 (같은 서비스 인스턴스로)
        chat_service = ChatService(
            chat_repository=ChatRepository(session),
            chat_message_repository=ChatMessageRepository(session),
        )

        # Mock ChatCompletion
        with patch("core.ai.azure_llm.AzureLLM.generate_text") as mock_generate_text:
            mock_generate_text.return_value = MockChatCompletion(
                choices=[
                    MockChatCompletionChoice(
                        message=MockChatCompletionMessage(
                            content="안녕하세요 테스트입니다"
                        )
                    )
                ]
            )

        # Mock ChatCompletion
        with patch("core.ai.azure_llm.AzureLLM.generate_text") as mock_generate_text:
            mock_generate_text.return_value = MockChatCompletion(
                choices=[
                    MockChatCompletionChoice(
                        message=MockChatCompletionMessage(
                            content="안녕하세요 테스트입니다"
                        )
                    )
                ]
            )

            # 첫 번째 채팅
            await chat_service.process_chat_message(
                ChatMessageRequestDTO(
                    chat_id="multi-chat-1",
                    user_id="multi-op-user",
                    message="첫 번째 메시지",
                )
            )

            # 두 번째 채팅
            await chat_service.process_chat_message(
                ChatMessageRequestDTO(
                    chat_id="multi-chat-2",
                    user_id="multi-op-user",
                    message="두 번째 메시지",
                )
            )

        # Then: 모든 데이터가 저장되었는지 확인
        chats = await session.execute(
            select(Chat).where(Chat.user_id == "multi-op-user")
        )
        chats = chats.scalars().all()
        assert len(chats) == 2

        messages = await session.execute(
            select(ChatMessage).where(
                ChatMessage.chat_id.in_(["multi-chat-1", "multi-chat-2"])
            )
        )
        messages = messages.scalars().all()
        assert len(messages) == 2
