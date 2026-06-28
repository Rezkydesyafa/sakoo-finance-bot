from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User
from app.modules.auth.dependencies import get_current_user
from app.modules.jobs.service import (
    JobQueueError,
    VoiceSttEnqueue,
    get_voice_stt_enqueue,
    queue_voice_stt_job,
)
from app.modules.stt.schemas import VoiceSttJobResponse, VoiceSttRequest


router = APIRouter(prefix="/stt", tags=["stt"])


@router.post(
    "/transcribe/{media_id}",
    response_model=VoiceSttJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def transcribe_voice_media(
    media_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    enqueue: Annotated[VoiceSttEnqueue, Depends(get_voice_stt_enqueue)],
) -> VoiceSttJobResponse:
    return _queue_voice_stt(
        media_id=media_id,
        current_user=current_user,
        db=db,
        enqueue=enqueue,
    )


@router.post(
    "/transcribe",
    response_model=VoiceSttJobResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
def transcribe_voice_media_from_body(
    payload: VoiceSttRequest,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    enqueue: Annotated[VoiceSttEnqueue, Depends(get_voice_stt_enqueue)],
) -> VoiceSttJobResponse:
    return _queue_voice_stt(
        media_id=payload.media_id,
        current_user=current_user,
        db=db,
        enqueue=enqueue,
    )


def _queue_voice_stt(
    *,
    media_id: int,
    current_user: User,
    db: Session,
    enqueue: VoiceSttEnqueue,
) -> VoiceSttJobResponse:
    try:
        job = queue_voice_stt_job(
            db,
            user_id=current_user.id,
            media_id=media_id,
            source="dashboard",
            enqueue=enqueue,
        )
    except JobQueueError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return VoiceSttJobResponse(job=job)
