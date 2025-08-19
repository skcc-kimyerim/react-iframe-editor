from fastapi import FastAPI
from .core.config import setup_middleware, setup_logging
from .core.lifecycle import lifespan
from .routers import health, files, components, devserver, chat, project
from .routers import uploads

# 로깅 초기화
logger = setup_logging()

def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    setup_middleware(app)
    logger.info("🚀 FastAPI application initialized")
    api_prefix = "/api"
    app.include_router(health.router, prefix=api_prefix)
    app.include_router(files.router, prefix=api_prefix)
    app.include_router(components.router, prefix=api_prefix)
    app.include_router(devserver.router, prefix=api_prefix)
    app.include_router(chat.router, prefix=api_prefix)
    app.include_router(project.router, prefix=api_prefix)
    app.include_router(uploads.router, prefix=api_prefix)
    return app


app = create_app()

