from pathlib import Path

from fastapi import (
    APIRouter,
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
)

router = APIRouter(
    prefix="/api/documents",
    tags=["Documents"],
)


def _owner_id(current_user):
    try:
        return int(current_user["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user token",
        ) from exc


def _not_found(exc):
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Document not found",
    ) from exc


class DocumentUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    category: str | None = Field(default=None, max_length=100)


@router.post("", status_code=status.HTTP_201_CREATED)
async def upload(
    file: UploadFile = File(...),
    title: str | None = Form(default=None),
    current_user: dict = Depends(get_current_user),
):
    try:
        content = await file.read()
        return upload_document(
            _owner_id(current_user),
            file.filename,
            content,
            title,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc


@router.get("")
def list_documents_endpoint(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=20, ge=1, le=100),
    current_user: dict = Depends(get_current_user),
):
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
    except FileNotFoundError as exc:
        _not_found(exc)


@router.get("/{document_id}")
def details(
    document_id: int,
    current_user: dict = Depends(get_current_user),
):
    try:
        return get_user_document(
            _owner_id(current_user),
            document_id,
        )
    except FileNotFoundError as exc:
        _not_found(exc)


@router.patch("/{document_id}")
def edit(
    document_id: int,
    request: DocumentUpdate,
    current_user: dict = Depends(get_current_user),
):
    try:
        return edit_user_document(
            _owner_id(current_user),
            document_id,
            request.dict(exclude_unset=True),
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    except FileNotFoundError as exc:
        _not_found(exc)


@router.delete(
    "/{document_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete(
    document_id: int,
    current_user: dict = Depends(get_current_user),
):
    try:
        delete_user_document(
            _owner_id(current_user),
            document_id,
        )
    except FileNotFoundError as exc:
        _not_found(exc)

    return Response(status_code=status.HTTP_204_NO_CONTENT)