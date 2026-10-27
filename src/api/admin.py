from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    status,
)
from pydantic import BaseModel, Field

from src.api.dependencies import get_current_user
from src.repositories.admin_repository import (
    list_categories,
    create_category,
    delete_category,
    record_audit_event,
    list_audit_events,
)

router = APIRouter(
    prefix="/api/admin",
    tags=["Administration"],
)


def _require_admin(current_user):
    role = str(current_user.get("role", "")).strip().lower()

    if role not in {"admin", "administrator"}:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Administrator access required",
        )

    try:
        user_id = int(current_user["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid user token",
        ) from exc

    return user_id


class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(min_length=1, max_length=500)


@router.get("/categories")
def get_categories(
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)
    return {"items": list_categories()}


@router.post(
    "/categories",
    status_code=status.HTTP_201_CREATED,
)
def add_category(
    request: CategoryCreate,
    current_user: dict = Depends(get_current_user),
):
    user_id = _require_admin(current_user)

    try:
        category = create_category(
            request.name,
            request.description,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    record_audit_event(
        user_id,
        current_user.get("username"),
        "category_created",
        f"Created category: {category['name']}",
    )

    return category


@router.delete("/categories/{category_id}")
def remove_category(
    category_id: int,
    current_user: dict = Depends(get_current_user),
):
    user_id = _require_admin(current_user)

    result = delete_category(category_id)

    if result is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )

    record_audit_event(
        user_id,
        current_user.get("username"),
        "category_deleted",
        (
            f"Deleted category: {result['category']['name']}; "
            f"documents reset: {result['documents_reset']}"
        ),
    )

    return result


@router.get("/audit-logs")
def get_audit_logs(
    page: int = Query(default=1, ge=1),
    current_user: dict = Depends(get_current_user),
):
    _require_admin(current_user)

    page_size = 10

    return list_audit_events(
        offset=(page - 1) * page_size,
        limit=page_size,
    )