from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Receipt, User
from app.modules.auth.dependencies import get_current_user
from app.modules.ocr.client import OcrClient, OcrClientError, get_ocr_client
from app.modules.ocr.schemas import ReceiptOcrResponse
from app.modules.ocr.service import ReceiptOcrError, process_receipt_ocr


router = APIRouter(prefix="/ocr", tags=["ocr"])


@router.post("/receipts/{media_id}", response_model=ReceiptOcrResponse)
def run_receipt_ocr(
    media_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    ocr_client: Annotated[OcrClient, Depends(get_ocr_client)],
) -> Receipt:
    try:
        return process_receipt_ocr(
            db,
            user_id=current_user.id,
            media_id=media_id,
            ocr_client=ocr_client,
        )
    except ReceiptOcrError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    except OcrClientError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
