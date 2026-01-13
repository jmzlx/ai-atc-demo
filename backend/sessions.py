"""Session management - list sessions and retrieve events for replay."""

import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

# Path to agent logs directory
AGENT_LOGS_DIR = Path(__file__).parent.parent.parent / "openscope-llm-agent" / "logs"

sessions_router = APIRouter(tags=["sessions"])


class SessionMetadata(BaseModel):
    """Metadata for a session."""

    session_id: str
    timestamp: str
    model: str | None = None
    airport: str | None = None
    duration_s: float | None = None
    score: int | None = None
    landings: int | None = None
    event_count: int = 0


class SessionEvent(BaseModel):
    """A single event from a session log."""

    timestamp: str
    game_time: float
    iteration: int
    event_type: str
    data: dict


def parse_session_id(filename: str) -> str | None:
    """Extract session ID from filename like 'events_atc_20260112_222918.jsonl'."""
    if filename.startswith("events_") and filename.endswith(".jsonl"):
        return filename[7:-6]  # Remove 'events_' prefix and '.jsonl' suffix
    return None


def load_session_metadata(log_path: Path) -> SessionMetadata | None:
    """Load metadata from a session log file."""
    session_id = parse_session_id(log_path.name)
    if not session_id:
        return None

    events = []
    metadata = {"session_id": session_id, "event_count": 0}

    try:
        with open(log_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    events.append(event)
                except json.JSONDecodeError:
                    continue

        metadata["event_count"] = len(events)

        # Extract metadata from session_start event
        for event in events:
            if event.get("event_type") == "session_start":
                meta = event.get("metadata", {})
                metadata["model"] = meta.get("model")
                metadata["timestamp"] = event.get("timestamp", "")
                break

        # Extract end metrics from session_end event
        for event in reversed(events):
            if event.get("event_type") == "session_end":
                summary = event.get("summary", {})
                metadata["duration_s"] = event.get("game_time", 0)
                metadata["score"] = summary.get("game_score")
                metadata["landings"] = summary.get("arrivals_landed", 0)
                break

        # Fallback timestamp from first event
        if not metadata.get("timestamp") and events:
            metadata["timestamp"] = events[0].get("timestamp", "")

        return SessionMetadata(**metadata)

    except Exception:
        return None


@sessions_router.get("/sessions", response_model=list[SessionMetadata])
async def list_sessions():
    """List all available sessions from the logs directory."""
    if not AGENT_LOGS_DIR.exists():
        return []

    sessions = []
    for log_file in AGENT_LOGS_DIR.glob("events_*.jsonl"):
        metadata = load_session_metadata(log_file)
        if metadata:
            sessions.append(metadata)

    # Sort by timestamp descending (newest first)
    sessions.sort(key=lambda s: s.timestamp or "", reverse=True)
    return sessions


@sessions_router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get metadata for a specific session."""
    log_path = AGENT_LOGS_DIR / f"events_{session_id}.jsonl"
    if not log_path.exists():
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    metadata = load_session_metadata(log_path)
    if not metadata:
        raise HTTPException(status_code=500, detail="Failed to load session metadata")

    return metadata


@sessions_router.get("/sessions/{session_id}/events")
async def get_session_events(session_id: str):
    """Get all events for a session (for replay)."""
    log_path = AGENT_LOGS_DIR / f"events_{session_id}.jsonl"
    if not log_path.exists():
        raise HTTPException(status_code=404, detail=f"Session not found: {session_id}")

    events = []
    try:
        with open(log_path) as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    events.append(event)
                except json.JSONDecodeError:
                    continue
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read events: {e}")

    return {"session_id": session_id, "events": events, "count": len(events)}
