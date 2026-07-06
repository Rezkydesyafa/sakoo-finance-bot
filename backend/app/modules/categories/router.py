from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.modules.auth.dependencies import get_current_user
from app.modules.categories.schemas import (
    CategoryCreateRequest,
    CategoryKeywordsRequest,
    CategoryListResponse,
    CategoryResponse,
    CategoryUpdateRequest,
)
from app.modules.categories.service import (
    category_exists,
    create_category,
    get_category,
    list_categories,
    soft_delete_category,
    update_category,
)


router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("", response_model=CategoryListResponse)
def list_user_categories(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CategoryListResponse:
    categories = list_categories(db, current_user.id)
    return CategoryListResponse(
        items=[CategoryResponse.model_validate(c) for c in categories],
        total=len(categories),
    )


@router.post(
    "",
    response_model=CategoryResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_user_category(
    payload: CategoryCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CategoryResponse:
    if category_exists(
        db,
        user_id=current_user.id,
        name=payload.name,
        type=payload.type,
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Category '{payload.name}' already exists for type '{payload.type}'",
        )

    category = create_category(
        db,
        user_id=current_user.id,
        name=payload.name,
        type=payload.type,
        icon=payload.icon,
        color=payload.color,
        keywords=payload.keywords,
    )
    db.commit()
    db.refresh(category)
    return CategoryResponse.model_validate(category)


@router.get("/{category_id}", response_model=CategoryResponse)
def get_user_category(
    category_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CategoryResponse:
    category = _get_visible_category(db, current_user.id, category_id)
    return CategoryResponse.model_validate(category)


@router.put("/{category_id}", response_model=CategoryResponse)
def update_user_category(
    category_id: int,
    payload: CategoryUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CategoryResponse:
    category = _get_owned_category(db, current_user.id, category_id)
    update_data = payload.model_dump(exclude_unset=True)

    if "name" in update_data or "type" in update_data:
        check_name = update_data.get("name", category.name)
        check_type = update_data.get("type", category.type)
        if category_exists(
            db,
            user_id=current_user.id,
            name=check_name,
            type=check_type,
            exclude_id=category_id,
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=f"Category '{check_name}' already exists for type '{check_type}'",
            )

    category = update_category(db, category, **update_data)
    db.commit()
    db.refresh(category)
    return CategoryResponse.model_validate(category)


@router.delete("/{category_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user_category(
    category_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    category = _get_owned_category(db, current_user.id, category_id)
    soft_delete_category(db, category)
    db.commit()


@router.patch("/{category_id}/keywords", response_model=CategoryResponse)
def update_category_keywords(
    category_id: int,
    payload: CategoryKeywordsRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> CategoryResponse:
    category = _get_owned_category(db, current_user.id, category_id)
    category = update_category(db, category, keywords=payload.keywords)
    db.commit()
    db.refresh(category)
    return CategoryResponse.model_validate(category)


def _get_visible_category(db: Session, user_id: int, category_id: int):
    """Get a category that is visible to this user (own or default)."""
    category = get_category(db, category_id)
    if category is None or not category.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )
    if category.user_id is not None and category.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )
    return category


def _get_owned_category(db: Session, user_id: int, category_id: int):
    """Get a category that belongs to this user (not default)."""
    category = get_category(db, category_id)
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Category not found",
        )
    if category.user_id != user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot modify default or another user's category",
        )
    return category
