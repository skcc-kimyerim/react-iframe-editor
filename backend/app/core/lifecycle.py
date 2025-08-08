from contextlib import asynccontextmanager
from fastapi import FastAPI
from ..services.react_dev_server import react_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    yield
    # shutdown
    await react_manager.stop()

