from figma2code.controller.converter_controller import (
    router as converter_router,
)
from fastapi import APIRouter

router = APIRouter()
router.include_router(converter_router)
