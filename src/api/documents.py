from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    Form,
    HTTPException,
    Query,
    Response,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from src.api.dependencies import get_current_user
from src.services.document_service import (
    upload_document,
    list_user_documents,
    get_user_document,
    get_download_info,
    edit_user_document,
    delete_user_document,
    process_document,
    queue_reprocessing,
)

router = APIRouter(
    prefix="/api/documents",
    tags=["Documents"],
)


def _owner_id(current_user):
    """Get the authenticated user's database ID."""
    try:
        return int(current_user["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user token",
        ) from exc


def _not_found():
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Document not found",
    )


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=100)


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
)
async def upload(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    current_user: dict = Depends(get_current_user),
):
    """Upload a document and schedule text extraction."""
    owner_id = _owner_id(current_user)

    try:
        content = await file.read()

        result = upload_document(
            owner_id,
            file.filename,
            content,
            title,
        )

        background_tasks.add_task(
            process_document,
            result["id"],
            owner_id,
        )

        return result

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    finally:
        await file.close()


@router.get("")
def list_documents_endpoint(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
    """List only the authenticated user's documents."""
    return list_user_documents(
        _owner_id(current_user),
        offset=offset,
        limit=limit,
    )


@router.get("/{document_id}/download")
def download(
    document_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Download the original document."""
    try:
        path, filename = get_download_info(
            _owner_id(current_user),
            document_id,
        )

        return FileResponse(
            path=str(path),
            filename=filename,
            media_type="application/octet-stream",
        )

    except FileNotFoundError:
        _not_found()


@router.get("/{document_id}")
def details(
    document_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Get details and processing status for an owned document."""
    try:
        return get_user_document(
            _owner_id(current_user),
            document_id,
        )

    except FileNotFoundError:
        _not_found()


@router.patch("/{document_id}")
def edit(
    document_id: int,
    request: DocumentUpdate,
    current_user: dict = Depends(get_current_user),
):
    """Update a document's title or category."""
    try:
        updates = request.model_dump(exclude_unset=True)

        return edit_user_document(
            _owner_id(current_user),
            document_id,
            updates,
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    except FileNotFoundError:
        _not_found()


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete(
    document_id: int,
    current_user: dict = Depends(get_current_user),
):
    """Permanently delete an owned document."""
    try:
        delete_user_document(
            _owner_id(current_user),
            document_id,
        )

    except FileNotFoundError:
        _not_found()

    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/{document_id}/reprocess",
    status_code=status.HTTP_202_ACCEPTED,
)
def reprocess(
    document_id: int,
    background_tasks: BackgroundTasks,
    current_user: dict = Depends(get_current_user),
):
    """Reprocess a previously Processed or Failed document."""
    owner_id = _owner_id(current_user)

    try:
        document = queue_reprocessing(
            owner_id,
            document_id,
        )

    except FileNotFoundError:
        _not_found()

    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    background_tasks.add_task(
        process_document,
        document_id,
        owner_id,
    )

    return {
        "id": document["id"],
        "processing_status": "Uploaded",
        "message": "Document reprocessing scheduled",
    }