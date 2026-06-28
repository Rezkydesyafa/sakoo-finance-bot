from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.modules.jobs.schemas import JobResponse


class VoiceNoteResponse(BaseModel):
    id: int
    user_id: int
    media_file_id: int
    transcript_text: str | None
    stt_provider: str | None
    transaction_id: int | None
    status: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class VoiceSttJobResponse(BaseModel):
    job: JobResponse
    message: str = "Voice STT job queued"


class VoiceSttRequest(BaseModel):
    media_id: int
