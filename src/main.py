
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.api.documents import router as documents_router
from src.api.auth import router as auth_router
from src.repositories.user_repository import init_db
from src.repositories.document_repository import migrate_document_schema
app = FastAPI(
    title="AI-CMS API",
    description="AI-Powered Content Management System",
    version="1.0.0",
)

# Allow the React frontend to call the backend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
)


@app.on_event("startup")
def startup():
    init_db()
    migrate_document_schema()


app.include_router(auth_router)
app.include_router(documents_router)

@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "AI-CMS backend",
    }
