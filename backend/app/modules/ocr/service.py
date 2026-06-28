from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import MediaFile, Receipt
from app.modules.media.service import (
    MediaStorageError,
    get_user_media_file,
    resolve_media_file_path,
)
from app.modules.ocr.client import OcrClient, OcrClientError
from app.modules.ocr.receipt_parser import parse_receipt_text


SUPPORTED_RECEIPT_OCR_MIME_TYPES = {"image/jpeg", "image/png", "image/webp"}


class ReceiptOcrError(Exception):
    def __init__(
        self,
        detail: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def process_receipt_ocr(
    db: Session,
    *,
    user_id: int,
    media_id: int,
    ocr_client: OcrClient,
) -> Receipt:
    media_file = _get_receipt_media_file(db, user_id=user_id, media_id=media_id)
    receipt = _get_or_create_receipt(db, user_id=user_id, media_file_id=media_file.id)

    try:
        file_path = resolve_media_file_path(media_file)
        result = ocr_client.extract_text(file_path.read_bytes())
    except MediaStorageError as exc:
        _mark_receipt_error(db, receipt)
        raise ReceiptOcrError(exc.detail, exc.status_code) from exc
    except OcrClientError:
        _mark_receipt_error(db, receipt)
        raise

    parse_result = parse_receipt_text(result.text)
    receipt.ocr_text = result.text
    receipt.merchant_name = parse_result.merchant_name
    receipt.receipt_date = parse_result.receipt_date
    receipt.total_amount = parse_result.total_amount
    receipt.confidence = parse_result.confidence
    receipt.status = parse_result.status
    db.commit()
    db.refresh(receipt)
    return receipt


def _get_receipt_media_file(db: Session, *, user_id: int, media_id: int) -> MediaFile:
    media_file = get_user_media_file(db, user_id=user_id, media_id=media_id)
    if media_file is None:
        raise ReceiptOcrError("Receipt media file not found", status.HTTP_404_NOT_FOUND)

    if media_file.file_type != "receipt":
        raise ReceiptOcrError(
            "Media file is not a receipt",
            status.HTTP_400_BAD_REQUEST,
        )

    if media_file.mime_type not in SUPPORTED_RECEIPT_OCR_MIME_TYPES:
        raise ReceiptOcrError(
            "Receipt OCR currently supports image/jpeg, image/png, and image/webp",
            status.HTTP_400_BAD_REQUEST,
        )

    return media_file


def _get_or_create_receipt(db: Session, *, user_id: int, media_file_id: int) -> Receipt:
    receipt = db.scalar(
        select(Receipt).where(
            Receipt.user_id == user_id,
            Receipt.media_file_id == media_file_id,
        )
    )
    if receipt is not None:
        return receipt

    receipt = Receipt(
        user_id=user_id,
        media_file_id=media_file_id,
        status="pending",
    )
    db.add(receipt)
    db.flush()
    return receipt


def _mark_receipt_error(db: Session, receipt: Receipt) -> None:
    receipt.status = "error"
    db.commit()
