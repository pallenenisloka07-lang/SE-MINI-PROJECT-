from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI

from backend.app.database.init_db import initialize_database
from src.api.auth import router as auth_router
from src.api.documents import router as documents_router
from src.repositories.user_repository import init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    initialize_database()
    yield


app = FastAPI(
    title="AI-CMS API",
    description="AI-Powered Content Management System",
    version="1.0.0",
    lifespan=lifespan,
)

app.include_router(auth_router)
app.include_router(documents_router)


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "AI-CMS backend"}
