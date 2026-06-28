from __future__ import annotations

import json
import shutil
import subprocess
import wave
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class AudioMetadata:
    duration_seconds: float | None = None
    sample_rate_hertz: int | None = None


def probe_audio_metadata(path: Path, *, mime_type: str | None = None) -> AudioMetadata:
    normalized_mime_type = _normalize_mime_type(mime_type)
    suffix = path.suffix.lower()

    if normalized_mime_type in {"audio/wav", "audio/wave", "audio/x-wav"} or suffix == ".wav":
        metadata = _probe_wav(path)
        if metadata.duration_seconds is not None:
            return metadata

    if normalized_mime_type in {"audio/ogg", "audio/oga", "audio/opus"} or suffix in {
        ".ogg",
        ".oga",
        ".opus",
    }:
        metadata = _probe_ogg_opus(path)
        if metadata.duration_seconds is not None:
            return metadata

    return _probe_with_ffprobe(path)


def _probe_wav(path: Path) -> AudioMetadata:
    try:
        with wave.open(str(path), "rb") as audio_file:
            frame_rate = audio_file.getframerate()
            frames = audio_file.getnframes()
    except (OSError, EOFError, wave.Error):
        return AudioMetadata()

    if frame_rate <= 0:
        return AudioMetadata()
    return AudioMetadata(
        duration_seconds=frames / frame_rate,
        sample_rate_hertz=frame_rate,
    )


def _probe_ogg_opus(path: Path) -> AudioMetadata:
    max_granule_position: int | None = None

    try:
        with path.open("rb") as audio_file:
            while True:
                header = audio_file.read(27)
                if not header:
                    break
                if len(header) < 27 or header[:4] != b"OggS":
                    return AudioMetadata()

                granule_position = int.from_bytes(header[6:14], "little", signed=True)
                segment_count = header[26]
                segment_table = audio_file.read(segment_count)
                if len(segment_table) != segment_count:
                    return AudioMetadata()

                audio_file.seek(sum(segment_table), 1)
                if granule_position >= 0:
                    max_granule_position = max(
                        granule_position,
                        max_granule_position or 0,
                    )
    except OSError:
        return AudioMetadata()

    if max_granule_position is None:
        return AudioMetadata()

    # Opus in Ogg always uses a 48 kHz granule clock.
    return AudioMetadata(
        duration_seconds=max_granule_position / 48_000,
        sample_rate_hertz=48_000,
    )


def _probe_with_ffprobe(path: Path) -> AudioMetadata:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return AudioMetadata()

    try:
        result = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration:stream=sample_rate",
                "-of",
                "json",
                str(path),
            ],
            capture_output=True,
            check=False,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return AudioMetadata()

    if result.returncode != 0:
        return AudioMetadata()

    try:
        payload = json.loads(result.stdout or "{}")
    except json.JSONDecodeError:
        return AudioMetadata()

    duration = _positive_float(payload.get("format", {}).get("duration"))
    sample_rate = None
    streams = payload.get("streams")
    if isinstance(streams, list):
        for stream in streams:
            if isinstance(stream, dict):
                sample_rate = _positive_int(stream.get("sample_rate"))
                if sample_rate is not None:
                    break

    return AudioMetadata(duration_seconds=duration, sample_rate_hertz=sample_rate)


def _normalize_mime_type(mime_type: str | None) -> str | None:
    if not mime_type:
        return None
    return mime_type.split(";", 1)[0].strip().lower() or None


def _positive_float(value: object) -> float | None:
    try:
        number = float(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _positive_int(value: object) -> int | None:
    try:
        number = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None
