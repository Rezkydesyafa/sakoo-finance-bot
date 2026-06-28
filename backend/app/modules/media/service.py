import mimetypes
import re
from datetime import date
from pathlib import Path
from uuid import uuid4

from fastapi import status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.models import MediaFile


ALLOWED_FILE_TYPES = {"receipt", "audio", "pdf"}
ALLOWED_RECEIPT_MIME_TYPES = {
    "application/pdf",
    "image/jpeg",
    "image/png",
    "image/webp",
}
ALLOWED_PDF_MIME_TYPES = {"application/pdf"}
SAFE_EXTENSION_PATTERN = re.compile(r"^\.[a-z0-9]{1,10}$")
SAFE_SOURCE_PATTERN = re.compile(r"^[a-z0-9_:-]{1,40}$")


class MediaStorageError(Exception):
    def __init__(
        self,
        detail: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
    ) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def normalize_media_file_type(file_type: str) -> str:
    normalized = file_type.strip().lower()
    if normalized not in ALLOWED_FILE_TYPES:
        raise MediaStorageError(
            "file_type must be one of: receipt, audio, pdf",
            status.HTTP_400_BAD_REQUEST,
        )
    return normalized


def max_upload_bytes_for_file_type(file_type: str) -> int:
    settings = get_settings()
    normalized = normalize_media_file_type(file_type)
    if normalized == "receipt":
        return settings.media_receipt_max_bytes
    return settings.media_default_max_bytes


def save_media_bytes(
    db: Session,
    *,
    user_id: int,
    file_type: str,
    content: bytes,
    original_filename: str | None,
    mime_type: str | None,
    source: str,
) -> MediaFile:
    normalized_type = normalize_media_file_type(file_type)
    normalized_mime_type = _normalize_mime_type(mime_type)
    normalized_source = _normalize_source(source)
    safe_original_filename = _safe_original_filename(original_filename)

    _validate_media_content(
        file_type=normalized_type,
        size=len(content),
        mime_type=normalized_mime_type,
    )

    relative_path = _build_relative_path(
        user_id=user_id,
        file_type=normalized_type,
        original_filename=safe_original_filename,
        mime_type=normalized_mime_type,
    )
    absolute_path = _resolve_under_storage_root(relative_path)
    absolute_path.parent.mkdir(parents=True, exist_ok=True)
    absolute_path.write_bytes(content)

    media_file = MediaFile(
        user_id=user_id,
        file_type=normalized_type,
        original_filename=safe_original_filename,
        stored_path=relative_path.as_posix(),
        mime_type=normalized_mime_type,
        size=len(content),
        source=normalized_source,
    )
    db.add(media_file)
    try:
        db.commit()
    except Exception:
        db.rollback()
        absolute_path.unlink(missing_ok=True)
        raise

    db.refresh(media_file)
    return media_file


def get_user_media_file(db: Session, *, user_id: int, media_id: int) -> MediaFile | None:
    return db.scalar(
        select(MediaFile).where(
            MediaFile.id == media_id,
            MediaFile.user_id == user_id,
        )
    )


def resolve_media_file_path(media_file: MediaFile) -> Path:
    absolute_path = _resolve_under_storage_root(Path(media_file.stored_path))
    if not absolute_path.is_file():
        raise MediaStorageError(
            "Media file is not available",
            status.HTTP_404_NOT_FOUND,
        )
    return absolute_path


def _validate_media_content(*, file_type: str, size: int, mime_type: str | None) -> None:
    if size <= 0:
        raise MediaStorageError("File is empty", status.HTTP_400_BAD_REQUEST)

    max_size = max_upload_bytes_for_file_type(file_type)
    if size > max_size:
        raise MediaStorageError(
            f"File size exceeds limit of {max_size} bytes for {file_type}",
            status.HTTP_413_CONTENT_TOO_LARGE,
        )

    if not _is_allowed_mime_type(file_type=file_type, mime_type=mime_type):
        raise MediaStorageError(
            f"MIME type is not allowed for {file_type}",
            status.HTTP_400_BAD_REQUEST,
        )


def _is_allowed_mime_type(*, file_type: str, mime_type: str | None) -> bool:
    if not mime_type:
        return False
    if file_type == "receipt":
        return mime_type in ALLOWED_RECEIPT_MIME_TYPES
    if file_type == "audio":
        return mime_type.startswith("audio/")
    if file_type == "pdf":
        return mime_type in ALLOWED_PDF_MIME_TYPES
    return False


def _build_relative_path(
    *,
    user_id: int,
    file_type: str,
    original_filename: str | None,
    mime_type: str | None,
) -> Path:
    today = date.today()
    extension = _safe_extension(original_filename, mime_type)
    return (
        Path(f"user_{user_id}")
        / file_type
        / f"{today:%Y}"
        / f"{today:%m}"
        / f"{uuid4().hex}{extension}"
    )


def _storage_root() -> Path:
    return Path(get_settings().storage_path).resolve()


def _resolve_under_storage_root(path: Path) -> Path:
    storage_root = _storage_root()
    candidate = path if path.is_absolute() else storage_root / path
    resolved = candidate.resolve()
    try:
        resolved.relative_to(storage_root)
    except ValueError as exc:
        raise MediaStorageError(
            "Stored media path is invalid",
            status.HTTP_500_INTERNAL_SERVER_ERROR,
        ) from exc
    return resolved


def _normalize_mime_type(mime_type: str | None) -> str | None:
    if not mime_type:
        return None
    return mime_type.split(";", 1)[0].strip().lower() or None


def _normalize_source(source: str) -> str:
    normalized = source.strip().lower()
    if not SAFE_SOURCE_PATTERN.fullmatch(normalized):
        raise MediaStorageError(
            "source must be 1-40 chars using lowercase letters, numbers, _, :, or -",
            status.HTTP_400_BAD_REQUEST,
        )
    return normalized


def _safe_original_filename(filename: str | None) -> str | None:
    if not filename:
        return None
    safe_name = Path(filename).name.strip()
    return safe_name[:255] or None


def _safe_extension(filename: str | None, mime_type: str | None) -> str:
    guessed = mimetypes.guess_extension(mime_type or "")
    if guessed and SAFE_EXTENSION_PATTERN.fullmatch(guessed.lower()):
        return guessed.lower()

    suffix = Path(filename or "").suffix.lower()
    if suffix and SAFE_EXTENSION_PATTERN.fullmatch(suffix):
        return suffix

    return ".bin"
