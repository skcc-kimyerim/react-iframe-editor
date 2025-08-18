from core.db.model.base import Base
from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
)
from sqlalchemy.sql import func


class ChatMessage(Base):
    __tablename__ = "ms_chat_messages"

    id = Column(String(36), primary_key=True)
    parent_id = Column(String(36), nullable=True)
    chat_id = Column(String(36), ForeignKey("ms_chats.id"), nullable=False)
    transaction_id = Column(String(36), nullable=True)
    role = Column(String(10), nullable=False)
    type = Column(String(10), nullable=False)
    intent_type = Column(String(10), nullable=True)
    content = Column(Text, nullable=False)
    content_metadata = Column(Text, nullable=True)
    message_metadata = Column(JSON, nullable=True)
    is_aborted = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
