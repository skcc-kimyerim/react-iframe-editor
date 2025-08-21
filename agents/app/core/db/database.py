# 모든 모델을 import하여 메타데이터에 등록
from core.config import get_setting
from core.db.connection import engine
from core.db.model.base import Base

# 모델이 추가되면 아래에 추가
_models = []


settings = get_setting()


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def close_db() -> None:
    try:
        if settings.ENVIRONMENT == "LOCAL":
            # 종료 시 모든 테이블을 삭제합니다.
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
        await engine.dispose()
    except Exception as e:
        raise e
