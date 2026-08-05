"""Run trace writer.

README section 8 wants ``trace.jsonl`` to hold the LATEST run only, so the file is
truncated once at startup and appended to thereafter. The trace is the evidence that
agents really handed off to each other instead of one prompt wearing eight name tags.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path
from typing import Any

from ec_dispute.config import metadata_document
from ec_dispute.contracts import A2AEnvelope, utc_now_z
from ec_dispute.paths import LOGGING_DIR

TRACE_PATH = LOGGING_DIR / "trace.jsonl"
METADATA_PATH = LOGGING_DIR / "metadata.json"

_lock = threading.Lock()


def start_run() -> None:
    """Truncate the trace and refresh metadata.json. Call once per full run."""
    LOGGING_DIR.mkdir(parents=True, exist_ok=True)
    TRACE_PATH.write_text("", encoding="utf-8")
    METADATA_PATH.write_text(json.dumps(metadata_document(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def record(event: dict[str, Any]) -> None:
    with _lock, TRACE_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"ts": utc_now_z(), **event}, ensure_ascii=False) + "\n")


def record_handoff(envelope: A2AEnvelope, *, latency_ms: int, tokens_in: int = 0, tokens_out: int = 0) -> None:
    record({
        "case_id": envelope.case_id,
        "stage": envelope.stage,
        "agent": envelope.from_agent,
        "to_agent": envelope.to_agent,
        "model": envelope.model,
        "event": "handoff",
        "payload_type": envelope.payload_type,
        "tool_calls": list(envelope.tool_calls),
        "latency_ms": latency_ms,
        "tokens": {"in": tokens_in, "out": tokens_out},
        "status": "ok",
    })


def record_error(case_id: str, agent: str, stage: str, message: str) -> None:
    record({"case_id": case_id, "agent": agent, "stage": stage, "event": "error", "status": "error", "message": message})


def read_trace() -> list[dict]:
    if not TRACE_PATH.exists():
        return []
    return [json.loads(line) for line in TRACE_PATH.read_text(encoding="utf-8").splitlines() if line.strip()]
