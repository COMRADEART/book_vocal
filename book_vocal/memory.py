from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Optional


def default_state_dir() -> Path:
    """Return the default directory for bubble memory state."""

    return Path.home() / ".book_vocal"


def compute_book_id(text: str) -> str:
    """Compute a stable identifier for the uploaded book contents."""

    digest = hashlib.sha1(text.encode("utf-8")).hexdigest()
    return digest


@dataclass
class BubbleMemory:
    """Stores the latest reading checkpoint for a book."""

    book_id: str
    last_index: int
    last_question: Optional[str]
    last_summary: Optional[str]
    updated_at: str


class BubbleMemoryStore:
    """Persist and retrieve bubble memories as JSON."""

    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self, book_id: str) -> Optional[BubbleMemory]:
        payload = self._load_payload()
        record = payload.get(book_id)
        if not record:
            return None
        return BubbleMemory(
            book_id=book_id,
            last_index=int(record.get("last_index", 0)),
            last_question=record.get("last_question"),
            last_summary=record.get("last_summary"),
            updated_at=str(record.get("updated_at", "")),
        )

    def save(self, memory: BubbleMemory) -> None:
        payload = self._load_payload()
        payload[memory.book_id] = {
            "last_index": memory.last_index,
            "last_question": memory.last_question,
            "last_summary": memory.last_summary,
            "updated_at": memory.updated_at,
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    def _load_payload(self) -> Dict[str, Dict[str, object]]:
        if not self.path.exists():
            return {}
        return json.loads(self.path.read_text(encoding="utf-8"))


def build_memory(
    book_id: str,
    *,
    last_index: int,
    last_question: Optional[str],
    last_summary: Optional[str],
) -> BubbleMemory:
    """Construct a bubble memory record with a current timestamp."""

    timestamp = datetime.now(timezone.utc).isoformat()
    return BubbleMemory(
        book_id=book_id,
        last_index=last_index,
        last_question=last_question,
        last_summary=last_summary,
        updated_at=timestamp,
    )
