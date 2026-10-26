from contextlib import asynccontextmanager

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.database.init_db import initialize_database
from src.api.auth import router as auth_router
from src.api.documents import router as documents_router
from src.api.search import router as search_router
from src.api.admin import router as admin_router

from src.repositories.user_repository import init_db
from src.repositories.document_repository import migrate_document_schema
from src.repositories.admin_repository import init_admin_tables



@asynccontextmanager
async def lifespan(app: FastAPI):
    # A FastAPI lifespan handler replaces deprecated startup event handlers.
    # Initialize both persistence layers and run their required migrations.
    init_db()
    migrate_document_schema()
    init_admin_tables()
    initialize_database()
    yield


app = FastAPI(
    title="AI-CMS API",
    description="AI-Powered Content Management System",
    version="1.0.0",
    lifespan=lifespan,
)

# Allow the React frontend to call the backend.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=[
        "GET",
        "POST",
        "PUT",
        "PATCH",
        "DELETE",
        "OPTIONS",
    ],
    allow_headers=[
        "Content-Type",
        "Authorization",
    ],
)


# Register each API router once.
app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(search_router)
app.include_router(admin_router)


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "AI-CMS backend"}
