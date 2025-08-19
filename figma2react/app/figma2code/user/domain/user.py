from core.db.model.base import Base
from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text
from sqlalchemy.sql import func


class User(Base):
    __tablename__ = "ms_users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(String(36), nullable=False, unique=True)
    email = Column(String(150), nullable=False, unique=True)
    username = Column(String(50), nullable=True)
    profile = Column(Text)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at = Column(DateTime(timezone=True), onupdate=func.now(), nullable=True)
