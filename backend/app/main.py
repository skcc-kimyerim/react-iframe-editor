from fastapi import FastAPI
from .core.config import setup_middleware
from .core.lifecycle import lifespan
from .routers import health, files, components, devserver, chat, project, figma


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    setup_middleware(app)
    api_prefix = "/api"
    app.include_router(health.router, prefix=api_prefix)
    app.include_router(files.router, prefix=api_prefix)
    app.include_router(components.router, prefix=api_prefix)
    app.include_router(devserver.router, prefix=api_prefix)
    app.include_router(chat.router, prefix=api_prefix)
    app.include_router(project.router, prefix=api_prefix)
    app.include_router(figma.router, prefix=api_prefix)
    return app


app = create_app()

