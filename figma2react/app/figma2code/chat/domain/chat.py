from core.db.model.base import Base
from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.sql import func


class Chat(Base):
    __tablename__ = "ms_chats"

    id = Column(String(36), primary_key=True)
    user_id = Column(String(36), ForeignKey("ms_users.user_id"), nullable=False)
    title = Column(Text, nullable=True)
    model = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    config_json = Column(Text, nullable=True)
