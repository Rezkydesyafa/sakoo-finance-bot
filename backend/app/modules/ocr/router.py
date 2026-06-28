from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.modules.auth.dependencies import get_current_user
from app.modules.jobs.service import (
    JobQueueError,
    ReceiptOcrEnqueue,
    get_receipt_ocr_enqueue,
    queue_receipt_ocr_job,
)
from app.modules.ocr.schemas import ReceiptOcrJobResponse


router = APIRouter(prefix="/ocr", tags=["ocr"])


@router.post(
    "/receipts/{media_id}",
    response_model=ReceiptOcrJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def run_receipt_ocr(
    media_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    enqueue: Annotated[ReceiptOcrEnqueue, Depends(get_receipt_ocr_enqueue)],
) -> ReceiptOcrJobResponse:
    try:
        job = queue_receipt_ocr_job(
            db,
            user_id=current_user.id,
            media_id=media_id,
            source="dashboard",
            enqueue=enqueue,
        )
    except JobQueueError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return ReceiptOcrJobResponse(job=job)
