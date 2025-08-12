from app.main import app  # expose FastAPI app

if __name__ == "__main__":
    import uvicorn
    import logging
    from app.core.config import settings, setup_logging

    # 로깅 초기화
    logger = setup_logging()
    
    logger.info(f"🚀 Backend server starting on http://localhost:{settings.PORT}")
    logger.info(f"📡 API endpoints available at http://localhost:{settings.PORT}/api/")
    
    uvicorn.run(
        "main:app", 
        host="0.0.0.0", 
        port=settings.PORT, 
        reload=True,
        log_level="info"
    )

