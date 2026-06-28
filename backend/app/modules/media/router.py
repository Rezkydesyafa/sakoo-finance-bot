from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import MediaFile, User
from app.modules.auth.dependencies import get_current_user
from app.modules.media.schemas import MediaFileResponse
from app.modules.media.service import (
    MediaStorageError,
    get_user_media_file,
    max_upload_bytes_for_file_type,
    normalize_media_file_type,
    resolve_media_file_path,
    save_media_bytes,
)


router = APIRouter(prefix="/media", tags=["media"])


@router.post("", response_model=MediaFileResponse, status_code=status.HTTP_201_CREATED)
async def upload_media_file(
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    file: Annotated[UploadFile, File()],
    file_type: Annotated[str, Form()],
    source: Annotated[str, Form()] = "dashboard_upload",
) -> MediaFile:
    try:
        normalized_type = normalize_media_file_type(file_type)
        max_size = max_upload_bytes_for_file_type(normalized_type)
        content = await file.read(max_size + 1)
        media_file = save_media_bytes(
            db,
            user_id=current_user.id,
            file_type=normalized_type,
            content=content,
            original_filename=file.filename,
            mime_type=file.content_type,
            source=source,
        )
    except MediaStorageError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc
    finally:
        await file.close()

    return media_file


@router.get("/{media_id}/download")
def download_media_file(
    media_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> FileResponse:
    media_file = get_user_media_file(db, user_id=current_user.id, media_id=media_id)
    if media_file is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Media file not found",
        )

    try:
        file_path = resolve_media_file_path(media_file)
    except MediaStorageError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from exc

    return FileResponse(
        path=file_path,
        media_type=media_file.mime_type or "application/octet-stream",
        filename=media_file.original_filename or file_path.name,
    )
