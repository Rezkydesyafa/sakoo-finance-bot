from pydantic import BaseModel

from app.modules.jobs.schemas import JobResponse


class VoiceSttJobResponse(BaseModel):
    job: JobResponse
    message: str = "Voice STT job queued"


class VoiceSttRequest(BaseModel):
    media_id: int
