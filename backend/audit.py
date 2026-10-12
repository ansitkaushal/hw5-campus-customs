"""Append-only audit trail at output/audit_trail.json (a JSON array; never wiped)."""

from __future__ import annotations

import json
import os
import threading

from .config import AUDIT_TRAIL
from .models import AuditEvent

_lock = threading.Lock()


def append(event: AuditEvent) -> None:
    """Append one event, keeping the file a valid JSON array. Writes atomically."""
    with _lock:
        AUDIT_TRAIL.parent.mkdir(parents=True, exist_ok=True)
        events: list = []
        if AUDIT_TRAIL.exists() and AUDIT_TRAIL.stat().st_size:
            events = json.loads(AUDIT_TRAIL.read_text())
        events.append(event.model_dump(mode="json", exclude_none=True))
        tmp = AUDIT_TRAIL.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(events, indent=2))
        os.replace(tmp, AUDIT_TRAIL)
