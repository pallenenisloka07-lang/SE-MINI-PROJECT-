from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Query, status

from src.api.dependencies import get_current_user
from src.services.search_service import (
    keyword_search,
    semantic_search,
)

router = APIRouter(
    prefix="/api/search",
    tags=["Search"],
)


def _owner_id(current_user):
    try:
        return int(current_user["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user token",
        ) from exc


def _validate_dates(date_from, date_to):
    if date_from and date_to and date_from > date_to:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Start date must not be after end date",
        )


@router.get("/keyword")
def keyword_search_endpoint(
    q: str = Query(..., min_length=1),
    category: str | None = None,
    file_type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    current_user: dict = Depends(get_current_user),
):
    _validate_dates(date_from, date_to)

    return keyword_search(
        owner_id=_owner_id(current_user),
        query=q,
        page=page,
        category=category,
        file_type=file_type,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/semantic")
def semantic_search_endpoint(
    q: str = Query(..., min_length=3, max_length=300),
    category: str | None = None,
    file_type: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    page: int = Query(default=1, ge=1),
    current_user: dict = Depends(get_current_user),
):
    _validate_dates(date_from, date_to)

    return semantic_search(
        owner_id=_owner_id(current_user),
        query=q,
        page=page,
        category=category,
        file_type=file_type,
        date_from=date_from,
        date_to=date_to,
    )