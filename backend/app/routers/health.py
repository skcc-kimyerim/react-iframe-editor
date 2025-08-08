from fastapi import APIRouter
from datetime import datetime

router = APIRouter(tags=["health"])


@router.get("/test")
async def test_endpoint():
    return {
        "message": "Backend server is running",
        "timestamp": datetime.now().isoformat(),
    }

