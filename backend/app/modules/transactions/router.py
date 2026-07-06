from datetime import date
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Category, Transaction, User
from app.modules.auth.dependencies import get_current_user
from app.modules.transactions.query import (
    TransactionQueryFilters,
    TransactionQueryResult,
    query_transactions,
)
from app.modules.transactions.schemas import (
    TransactionCreateRequest,
    TransactionListResponse,
    TransactionResponse,
    TransactionTextParseRequest,
    TransactionTextParseResponse,
    TransactionUpdateRequest,
)
from app.modules.transactions.service import handle_text_transaction


router = APIRouter(prefix="/transactions", tags=["transactions"])


@router.post(
    "",
    response_model=TransactionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_transaction(
    payload: TransactionCreateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Transaction:
    category = _get_category_for_type(db, payload.category_id, payload.type)
    transaction = Transaction(
        user_id=current_user.id,
        type=payload.type,
        amount=payload.amount,
        category_id=category.id if category else None,
        description=payload.description,
        transaction_date=payload.transaction_date,
        source="dashboard_manual",
        status="confirmed",
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


@router.get("", response_model=TransactionListResponse)
def list_transactions(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
    category_id: Annotated[int | None, Query(gt=0)] = None,
    transaction_type: Annotated[
        str | None,
        Query(alias="type", pattern="^(income|expense)$"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TransactionListResponse:
    _validate_date_range(start_date, end_date)
    result = query_transactions(
        db,
        TransactionQueryFilters(
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
            category_id=category_id,
            type=transaction_type,
            limit=limit,
            offset=offset,
        ),
    )
    return _to_list_response(result)


@router.get("/query", response_model=TransactionListResponse)
def query_transaction_history(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    start_date: Annotated[date | None, Query()] = None,
    end_date: Annotated[date | None, Query()] = None,
    category_id: Annotated[int | None, Query(gt=0)] = None,
    transaction_type: Annotated[
        str | None,
        Query(alias="type", pattern="^(income|expense)$"),
    ] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> TransactionListResponse:
    _validate_date_range(start_date, end_date)

    result = query_transactions(
        db,
        TransactionQueryFilters(
            user_id=current_user.id,
            start_date=start_date,
            end_date=end_date,
            category_id=category_id,
            type=transaction_type,
            limit=limit,
            offset=offset,
        ),
    )
    return _to_list_response(result)


@router.post("/parse", response_model=TransactionTextParseResponse)
def parse_transaction_text_from_dashboard(
    payload: TransactionTextParseRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> TransactionTextParseResponse:
    result = handle_text_transaction(
        db=db,
        user_id=current_user.id,
        text=payload.text,
        source="dashboard_manual",
    )
    db.commit()
    return TransactionTextParseResponse(
        status=result.status,
        reply_text=result.reply_text,
        transaction_id=result.transaction_id,
    )


def _to_list_response(result: TransactionQueryResult) -> TransactionListResponse:
    return TransactionListResponse(
        items=result.items,
        total=result.total,
        limit=result.limit,
        offset=result.offset,
        has_next=result.has_next,
    )


def _validate_date_range(start_date: date | None, end_date: date | None) -> None:
    if start_date and end_date and start_date > end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date cannot be after end_date",
        )


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Transaction:
    return _get_user_transaction(db, current_user.id, transaction_id)


@router.put("/{transaction_id}", response_model=TransactionResponse)
def update_transaction(
    transaction_id: int,
    payload: TransactionUpdateRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Transaction:
    transaction = _get_user_transaction(db, current_user.id, transaction_id)
    update_data = payload.model_dump(exclude_unset=True)
    next_type = update_data.get("type", transaction.type)

    if "category_id" in update_data:
        category = _get_category_for_type(db, update_data["category_id"], next_type)
        transaction.category_id = category.id if category else None
    elif "type" in update_data and transaction.category_id is not None:
        _get_category_for_type(db, transaction.category_id, next_type)

    if "type" in update_data:
        transaction.type = update_data["type"]
    if "amount" in update_data:
        transaction.amount = update_data["amount"]
    if "description" in update_data:
        transaction.description = update_data["description"]
    if "transaction_date" in update_data:
        transaction.transaction_date = update_data["transaction_date"]

    db.commit()
    db.refresh(transaction)
    return transaction


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> Response:
    transaction = _get_user_transaction(db, current_user.id, transaction_id)
    db.delete(transaction)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _get_user_transaction(db: Session, user_id: int, transaction_id: int) -> Transaction:
    transaction = db.scalar(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == user_id,
        )
    )
    if transaction is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaction not found",
        )
    return transaction


def _get_category_for_type(
    db: Session,
    category_id: int | None,
    transaction_type: str,
) -> Category | None:
    if category_id is None:
        return None

    category = db.get(Category, category_id)
    if category is None or category.type != transaction_type:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Category is not valid for this transaction type",
        )
    return category
