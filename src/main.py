import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware

from src.api.auth import router as auth_router
from src.api.documents import router as documents_router
from src.api.search import router as search_router
from src.api.admin import router as admin_router

from src.repositories.user_repository import init_db
from src.repositories.document_repository import (
    migrate_document_schema,
    list_processing_documents,
    mark_document_uploaded,
)
from src.repositories.admin_repository import init_admin_tables
from src.services.document_service import process_document

logger = logging.getLogger(__name__)


async def recover_interrupted_documents():
    """Reset interrupted documents and process them after startup."""
    documents = await asyncio.to_thread(list_processing_documents)

    for document in documents:
        document_id = document["id"]
        owner_id = document["owner_id"]

        try:
            updated = await asyncio.to_thread(
                mark_document_uploaded,
                document_id,
                owner_id,
            )

            if updated is not None:
                await asyncio.to_thread(
                    process_document,
                    document_id,
                    owner_id,
                )
        except Exception:
            logger.exception(
                "Could not recover document %s",
                document_id,
            )


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize database tables before applying schema migrations.
    init_db()
    migrate_document_schema()
    init_admin_tables()

    # Start recovery without blocking application startup.
    recovery_task = asyncio.create_task(
        recover_interrupted_documents()
    )
    app.state.recovery_task = recovery_task

    try:
        yield
    finally:
        recovery_task.cancel()
        try:
            await recovery_task
        except asyncio.CancelledError:
            pass


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


# Register all API routers.
app.include_router(auth_router)
app.include_router(documents_router)
app.include_router(search_router)
app.include_router(admin_router)


@app.get("/health")
def health_check():
    return {
        "status": "healthy",
        "service": "AI-CMS backend",
    }
