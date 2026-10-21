from fastapi import FastAPI

from src.api.auth import router as auth_router
from src.repositories.user_repository import init_db

app = FastAPI(
    title="AI-CMS API",
    description="AI-Powered Content Management System",
    version="1.0.0",
)


@app.on_event("startup")
def startup():
    init_db()


app.include_router(auth_router)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "AI-CMS backend",
    }