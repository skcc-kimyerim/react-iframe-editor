from contextlib import asynccontextmanager
from typing import AsyncGenerator

from core.config import get_setting
from core.db.database import close_db, init_db
from core.log.logging import get_logging
from fastapi import FastAPI
from figma2code.web.router import router

settings = get_setting()

logger = get_logging()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    try:
        logger.info("Initializing database")
        await init_db()
        yield
    except Exception as e:
        logger.error(f"Error initializing database: {e}")
        raise e
    finally:
        await close_db()


app = FastAPI(
    title="GenAI Boilerplate",
    description="GenAI Boilerplate",
    version="1.0.0",
    lifespan=lifespan,
)

# 라우터 등록
app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        app,
        host=settings.APP_HOST,
        port=settings.APP_PORT,
        access_log=False,
    )
