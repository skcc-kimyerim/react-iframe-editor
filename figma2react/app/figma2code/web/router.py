from fastapi import APIRouter
from figma2code.chat.controller.chat_controller import router as chat_router

router = APIRouter()
router.include_router(chat_router)
