from datetime import datetime

from pydantic import BaseModel, ConfigDict


class MediaFileResponse(BaseModel):
    id: int
    file_type: str
    original_filename: str | None
    mime_type: str | None
    size: int | None
    source: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
