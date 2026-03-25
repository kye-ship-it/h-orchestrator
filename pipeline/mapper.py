"""Data mapper: transforms raw BigQuery rows into the logging protocol."""

import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Column name constants — adjust these when actual BQ schema is confirmed.
# ---------------------------------------------------------------------------
COL_SESSION_ID = "session_id"
COL_CALL_ID = "call_id"
COL_TIMESTAMP = "timestamp"
COL_EVENT_TYPE = "event_type"
COL_ACTOR = "actor"
COL_PHONE_NUMBER = "phone_number"
COL_DURATION = "duration_seconds"
COL_STATUS = "call_status"
COL_TRANSFER = "transferred"
COL_TRANSFER_TARGET = "transfer_target"
COL_BANT_BUDGET = "bant_budget"
COL_BANT_AUTHORITY = "bant_authority"
COL_BANT_NEED = "bant_need"
COL_BANT_TIMELINE = "bant_timeline"
COL_QUESTION_TEXT = "question_text"
COL_ANSWER_TEXT = "answer_text"
COL_GREETING_TEXT = "greeting_text"
COL_SOURCE = "source"
COL_DISPOSITION = "disposition"
COL_ERROR_REASON = "error_reason"

# Valid event types for the logging protocol.
VALID_EVENT_TYPES = frozenset(
    {
        "call_queued",
        "call_dialed",
        "call_accepted",
        "greeting",
        "question_asked",
        "question_answered",
        "transfer",
        "call_ended",
    }
)

# Default actor mapping by event type when actor column is absent.
DEFAULT_ACTOR_MAP: dict[str, str] = {
    "call_queued": "system",
    "call_dialed": "system",
    "call_accepted": "customer",
    "greeting": "ai",
    "question_asked": "ai",
    "question_answered": "customer",
    "transfer": "system",
    "call_ended": "system",
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class Event:
    event_id: str
    event_type: str
    timestamp: datetime
    actor: str  # ai / customer / system
    payload: dict[str, Any]


@dataclass
class Session:
    session_id: str
    start_time: datetime
    end_time: datetime
    source: str
    events: list[Event] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class DailyMetrics:
    date: str
    total_calls: int
    connected_calls: int
    connection_rate: float
    bant_completion_rate: float
    avg_duration_seconds: float
    transfer_rate: float
    success_sessions: list[Session] = field(default_factory=list)
    failure_sessions: list[Session] = field(default_factory=list)
    anomalies: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _safe_get(row: dict, key: str, default: Any = None) -> Any:
    """Case-insensitive dict lookup with fallback."""
    if key in row:
        return row[key]
    key_lower = key.lower()
    for k, v in row.items():
        if k.lower() == key_lower:
            return v
    return default


def _parse_timestamp(value: Any) -> datetime:
    """Parse a timestamp value from various formats."""
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        return datetime.utcfromtimestamp(value)
    if isinstance(value, str):
        for fmt in (
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%f",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
        ):
            try:
                return datetime.strptime(value, fmt)
            except ValueError:
                continue
    raise ValueError(f"Cannot parse timestamp: {value!r}")


def _extract_bant(row: dict) -> dict[str, Any]:
    """Extract BANT fields from a row."""
    bant: dict[str, Any] = {}
    for label, col in (
        ("budget", COL_BANT_BUDGET),
        ("authority", COL_BANT_AUTHORITY),
        ("need", COL_BANT_NEED),
        ("timeline", COL_BANT_TIMELINE),
    ):
        val = _safe_get(row, col)
        if val is not None:
            bant[label] = val
    return bant


def _bant_complete(bant: dict[str, Any]) -> bool:
    """Check whether all four BANT fields are present and non-empty."""
    return all(bant.get(k) for k in ("budget", "authority", "need", "timeline"))


def _build_event(row: dict) -> Event:
    """Build an Event from a single BQ row."""
    raw_type = _safe_get(row, COL_EVENT_TYPE, "unknown")
    event_type = raw_type if raw_type in VALID_EVENT_TYPES else "unknown"

    actor = _safe_get(row, COL_ACTOR) or DEFAULT_ACTOR_MAP.get(event_type, "system")

    payload: dict[str, Any] = {}
    for col in (
        COL_QUESTION_TEXT,
        COL_ANSWER_TEXT,
        COL_GREETING_TEXT,
        COL_TRANSFER_TARGET,
        COL_ERROR_REASON,
        COL_DISPOSITION,
    ):
        val = _safe_get(row, col)
        if val is not None:
            payload[col] = val

    ts = _parse_timestamp(_safe_get(row, COL_TIMESTAMP, datetime.utcnow()))

    return Event(
        event_id=str(uuid.uuid4()),
        event_type=event_type,
        timestamp=ts,
        actor=actor,
        payload=payload,
    )


def _is_connected(session: Session) -> bool:
    """Determine if a session represents a connected call."""
    event_types = {e.event_type for e in session.events}
    # A call is considered connected if it was accepted or had a greeting.
    return bool(event_types & {"call_accepted", "greeting", "question_asked", "question_answered"})


def _is_success(session: Session) -> bool:
    """Determine if a session is successful.

    Success = connected AND (BANT completion OR dealer transfer).
    """
    if not _is_connected(session):
        return False
    has_transfer = any(e.event_type == "transfer" for e in session.events)
    bant = session.metadata.get("bant", {})
    return has_transfer or _bant_complete(bant)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------
def map_to_sessions(raw_rows: list[dict[str, Any]]) -> list[Session]:
    """Convert raw BigQuery rows into Session objects grouped by session/call ID.

    Each row is expected to represent a single event. Rows are grouped by
    session_id (falling back to call_id), then sorted chronologically.
    """
    if not raw_rows:
        return []

    # Group rows by session identifier.
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in raw_rows:
        sid = (
            _safe_get(row, COL_SESSION_ID)
            or _safe_get(row, COL_CALL_ID)
            or str(uuid.uuid4())
        )
        groups[str(sid)].append(row)

    sessions: list[Session] = []
    for session_id, rows in groups.items():
        events = [_build_event(r) for r in rows]
        events.sort(key=lambda e: e.timestamp)

        start_time = events[0].timestamp
        end_time = events[-1].timestamp

        # Aggregate metadata from all rows in the session.
        first_row = rows[0]
        bant = _extract_bant(first_row)
        # Merge BANT across all rows (later rows may have more answers).
        for r in rows[1:]:
            for k, v in _extract_bant(r).items():
                if v and not bant.get(k):
                    bant[k] = v

        duration = _safe_get(first_row, COL_DURATION)
        if duration is None:
            duration = (end_time - start_time).total_seconds()

        metadata: dict[str, Any] = {
            "bant": bant,
            "bant_complete": _bant_complete(bant),
            "call_status": _safe_get(first_row, COL_STATUS, "unknown"),
            "duration_seconds": float(duration) if duration is not None else 0.0,
            "transferred": any(e.event_type == "transfer" for e in events),
            "phone_number": _safe_get(first_row, COL_PHONE_NUMBER),
            "disposition": _safe_get(first_row, COL_DISPOSITION),
        }

        sessions.append(
            Session(
                session_id=session_id,
                start_time=start_time,
                end_time=end_time,
                source=_safe_get(first_row, COL_SOURCE, "h-voice"),
                events=events,
                metadata=metadata,
            )
        )

    sessions.sort(key=lambda s: s.start_time)
    logger.info("Mapped %d rows into %d sessions", len(raw_rows), len(sessions))
    return sessions


def compute_daily_metrics(sessions: list[Session]) -> DailyMetrics:
    """Aggregate session-level data into daily metrics."""
    if not sessions:
        return DailyMetrics(
            date="",
            total_calls=0,
            connected_calls=0,
            connection_rate=0.0,
            bant_completion_rate=0.0,
            avg_duration_seconds=0.0,
            transfer_rate=0.0,
        )

    date_str = sessions[0].start_time.strftime("%Y-%m-%d")
    total = len(sessions)

    connected = [s for s in sessions if _is_connected(s)]
    connected_count = len(connected)
    connection_rate = (connected_count / total * 100) if total else 0.0

    bant_complete_count = sum(
        1 for s in sessions if s.metadata.get("bant_complete", False)
    )
    bant_completion_rate = (bant_complete_count / total * 100) if total else 0.0

    durations = [
        s.metadata.get("duration_seconds", 0.0)
        for s in connected
        if s.metadata.get("duration_seconds", 0.0) > 0
    ]
    avg_duration = sum(durations) / len(durations) if durations else 0.0

    transfer_count = sum(1 for s in sessions if s.metadata.get("transferred", False))
    transfer_rate = (transfer_count / total * 100) if total else 0.0

    success = [s for s in sessions if _is_success(s)]
    failure = [s for s in sessions if not _is_success(s)]

    # Detect anomalies.
    anomalies: list[str] = []
    if connection_rate < 30.0:
        anomalies.append(f"Low connection rate: {connection_rate:.1f}%")
    if avg_duration < 10.0 and connected_count > 0:
        anomalies.append(f"Unusually short avg call duration: {avg_duration:.1f}s")
    if avg_duration > 600.0:
        anomalies.append(f"Unusually long avg call duration: {avg_duration:.1f}s")
    if bant_completion_rate < 10.0 and connected_count > 5:
        anomalies.append(f"Very low BANT completion rate: {bant_completion_rate:.1f}%")

    # Check for sessions with unknown event types.
    unknown_event_sessions = sum(
        1
        for s in sessions
        if any(e.event_type == "unknown" for e in s.events)
    )
    if unknown_event_sessions > 0:
        anomalies.append(
            f"{unknown_event_sessions} session(s) contain unrecognized event types"
        )

    return DailyMetrics(
        date=date_str,
        total_calls=total,
        connected_calls=connected_count,
        connection_rate=round(connection_rate, 2),
        bant_completion_rate=round(bant_completion_rate, 2),
        avg_duration_seconds=round(avg_duration, 2),
        transfer_rate=round(transfer_rate, 2),
        success_sessions=success,
        failure_sessions=failure,
        anomalies=anomalies,
    )
