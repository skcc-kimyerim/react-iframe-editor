from figma2code.convert_html.controller.convert_html_controller import (
    router as convert_html_router,
)
from fastapi import APIRouter

router = APIRouter()
router.include_router(convert_html_router)
