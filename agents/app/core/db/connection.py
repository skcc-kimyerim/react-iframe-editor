from typing import AsyncGenerator

from core.config import get_setting
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

setting = get_setting()

engine = create_async_engine(
    setting.DATABASE_URL, connect_args={"check_same_thread": False}
)

SessionLocal = async_sessionmaker(bind=engine, expire_on_commit=False)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    session = SessionLocal()
    try:
        yield session
    except Exception as e:
        await session.rollback()
        raise e
    finally:
        await session.close()
