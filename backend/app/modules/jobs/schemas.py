from datetime import datetime

from pydantic import BaseModel, ConfigDict


class JobResponse(BaseModel):
    id: int
    user_id: int
    job_type: str
    status: str
    result_id: int | None
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None

    model_config = ConfigDict(from_attributes=True)


class QueuedJobResponse(BaseModel):
    job: JobResponse
    message: str
