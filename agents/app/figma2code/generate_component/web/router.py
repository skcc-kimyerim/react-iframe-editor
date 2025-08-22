from figma2code.generate_component.controller.generate_component_controller import (
    router as generate_component_router,
)
from fastapi import APIRouter

router = APIRouter()
router.include_router(generate_component_router)
