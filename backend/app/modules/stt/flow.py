from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class VoiceSttFlowResult:
    status: str
    reply_text: str | None = None
    media_file_id: int | None = None
    voice_note_id: int | None = None
    job_id: int | None = None
    transaction_id: int | None = None
    error_message: str | None = None

    def to_log_payload(self) -> dict[str, Any]:
        return asdict(self)
