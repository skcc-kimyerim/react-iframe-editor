from figma2code.generate_page.controller.generate_page_controller import (
    router as generate_page_router,
)
from fastapi import APIRouter

router = APIRouter()
router.include_router(generate_page_router)
