from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.modules.jobs.schemas import JobResponse


class ReceiptOcrResponse(BaseModel):
    id: int
    user_id: int
    media_file_id: int
    ocr_text: str | None
    merchant_name: str | None
    receipt_date: date | None
    total_amount: Decimal | None
    confidence: Decimal | None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ReceiptOcrJobResponse(BaseModel):
    job: JobResponse
    message: str = "Receipt OCR job queued"
