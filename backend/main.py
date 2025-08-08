from app.main import app  # expose FastAPI app

if __name__ == "__main__":
    import uvicorn
    from app.core.config import settings

    print(f"🚀 Backend server running on http://localhost:{settings.PORT}")
    print(f"📡 API endpoints available at http://localhost:{settings.PORT}/api/")
    uvicorn.run("main:app", host="0.0.0.0", port=settings.PORT, reload=True)

