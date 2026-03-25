"""Unit tests for pipeline.mapper module."""

import pytest
from datetime import datetime

from pipeline.mapper import (
    Event,
    Session,
    DailyMetrics,
    map_to_sessions,
    compute_daily_metrics,
    _parse_timestamp,
    _safe_get,
    _extract_bant,
    _bant_complete,
    COL_SESSION_ID,
    COL_TIMESTAMP,
    COL_EVENT_TYPE,
    COL_ACTOR,
    COL_DURATION,
    COL_STATUS,
    COL_TRANSFER,
    COL_BANT_BUDGET,
    COL_BANT_AUTHORITY,
    COL_BANT_NEED,
    COL_BANT_TIMELINE,
    COL_SOURCE,
    COL_DISPOSITION,
    COL_QUESTION_TEXT,
    COL_ANSWER_TEXT,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def _make_row(
    session_id: str = "sess-001",
    event_type: str = "call_queued",
    timestamp: str = "2026-03-24T10:00:00Z",
    actor: str | None = None,
    duration: float | None = None,
    status: str = "completed",
    bant_budget: str | None = None,
    bant_authority: str | None = None,
    bant_need: str | None = None,
    bant_timeline: str | None = None,
    source: str = "h-voice",
    disposition: str | None = None,
    question: str | None = None,
    answer: str | None = None,
    **extra,
) -> dict:
    """Helper to build a mock BQ row dict."""
    row = {
        COL_SESSION_ID: session_id,
        COL_EVENT_TYPE: event_type,
        COL_TIMESTAMP: timestamp,
        COL_STATUS: status,
        COL_SOURCE: source,
    }
    if actor is not None:
        row[COL_ACTOR] = actor
    if duration is not None:
        row[COL_DURATION] = duration
    if bant_budget is not None:
        row[COL_BANT_BUDGET] = bant_budget
    if bant_authority is not None:
        row[COL_BANT_AUTHORITY] = bant_authority
    if bant_need is not None:
        row[COL_BANT_NEED] = bant_need
    if bant_timeline is not None:
        row[COL_BANT_TIMELINE] = bant_timeline
    if disposition is not None:
        row[COL_DISPOSITION] = disposition
    if question is not None:
        row[COL_QUESTION_TEXT] = question
    if answer is not None:
        row[COL_ANSWER_TEXT] = answer
    row.update(extra)
    return row


def _make_successful_call(session_id: str = "sess-ok-001", base_time: str = "2026-03-24T10:00:") -> list[dict]:
    """Build a sequence of rows representing a successful call with BANT and transfer."""
    return [
        _make_row(session_id=session_id, event_type="call_queued", timestamp=f"{base_time}00Z", duration=120),
        _make_row(session_id=session_id, event_type="call_dialed", timestamp=f"{base_time}05Z", duration=120),
        _make_row(session_id=session_id, event_type="call_accepted", timestamp=f"{base_time}10Z", duration=120),
        _make_row(session_id=session_id, event_type="greeting", timestamp=f"{base_time}12Z", duration=120),
        _make_row(
            session_id=session_id, event_type="question_asked", timestamp=f"{base_time}20Z",
            question="What is your budget?", duration=120,
        ),
        _make_row(
            session_id=session_id, event_type="question_answered", timestamp=f"{base_time}30Z",
            answer="Around $50k", duration=120,
            bant_budget="$50k", bant_authority="yes", bant_need="new vehicle", bant_timeline="this month",
        ),
        _make_row(session_id=session_id, event_type="transfer", timestamp=f"{base_time}40Z", duration=120),
        _make_row(session_id=session_id, event_type="call_ended", timestamp=f"{base_time}50Z", duration=120, disposition="transferred"),
    ]


def _make_failed_call(session_id: str = "sess-fail-001", base_time: str = "2026-03-24T11:00:") -> list[dict]:
    """Build rows for a call that was dialed but never connected."""
    return [
        _make_row(session_id=session_id, event_type="call_queued", timestamp=f"{base_time}00Z"),
        _make_row(session_id=session_id, event_type="call_dialed", timestamp=f"{base_time}05Z"),
        _make_row(session_id=session_id, event_type="call_ended", timestamp=f"{base_time}35Z", status="no_answer", disposition="no_answer"),
    ]


# ---------------------------------------------------------------------------
# Tests: helpers
# ---------------------------------------------------------------------------
class TestSafeGet:
    def test_exact_key(self):
        assert _safe_get({"foo": 1}, "foo") == 1

    def test_case_insensitive(self):
        assert _safe_get({"Foo": 2}, "foo") == 2

    def test_missing_returns_default(self):
        assert _safe_get({"a": 1}, "b", "default") == "default"

    def test_none_value(self):
        assert _safe_get({"a": None}, "a") is None


class TestParseTimestamp:
    def test_iso_format_z(self):
        dt = _parse_timestamp("2026-03-24T10:00:00Z")
        assert dt == datetime(2026, 3, 24, 10, 0, 0)

    def test_iso_format_microseconds(self):
        dt = _parse_timestamp("2026-03-24T10:00:00.123456Z")
        assert dt.year == 2026

    def test_datetime_passthrough(self):
        now = datetime.utcnow()
        assert _parse_timestamp(now) is now

    def test_unix_timestamp(self):
        dt = _parse_timestamp(1742817600.0)
        assert isinstance(dt, datetime)

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            _parse_timestamp("not-a-date")


class TestBantExtraction:
    def test_full_bant(self):
        row = {
            COL_BANT_BUDGET: "50k",
            COL_BANT_AUTHORITY: "yes",
            COL_BANT_NEED: "SUV",
            COL_BANT_TIMELINE: "Q1",
        }
        bant = _extract_bant(row)
        assert _bant_complete(bant) is True

    def test_partial_bant(self):
        row = {COL_BANT_BUDGET: "50k", COL_BANT_NEED: "SUV"}
        bant = _extract_bant(row)
        assert _bant_complete(bant) is False
        assert bant["budget"] == "50k"

    def test_empty_bant(self):
        bant = _extract_bant({})
        assert _bant_complete(bant) is False


# ---------------------------------------------------------------------------
# Tests: map_to_sessions
# ---------------------------------------------------------------------------
class TestMapToSessions:
    def test_empty_input(self):
        result = map_to_sessions([])
        assert result == []

    def test_single_session(self):
        rows = _make_successful_call()
        sessions = map_to_sessions(rows)
        assert len(sessions) == 1
        assert sessions[0].session_id == "sess-ok-001"
        assert len(sessions[0].events) == 8

    def test_multiple_sessions(self):
        rows = _make_successful_call("s1") + _make_failed_call("s2")
        sessions = map_to_sessions(rows)
        assert len(sessions) == 2
        ids = {s.session_id for s in sessions}
        assert ids == {"s1", "s2"}

    def test_events_sorted_chronologically(self):
        rows = [
            _make_row(session_id="s1", event_type="call_ended", timestamp="2026-03-24T10:05:00Z"),
            _make_row(session_id="s1", event_type="call_queued", timestamp="2026-03-24T10:00:00Z"),
        ]
        sessions = map_to_sessions(rows)
        assert sessions[0].events[0].event_type == "call_queued"
        assert sessions[0].events[1].event_type == "call_ended"

    def test_start_end_times(self):
        rows = _make_successful_call()
        sessions = map_to_sessions(rows)
        s = sessions[0]
        assert s.start_time < s.end_time

    def test_bant_merged_across_rows(self):
        rows = [
            _make_row(session_id="s1", event_type="question_answered", timestamp="2026-03-24T10:00:00Z", bant_budget="50k"),
            _make_row(session_id="s1", event_type="question_answered", timestamp="2026-03-24T10:01:00Z", bant_need="SUV"),
        ]
        sessions = map_to_sessions(rows)
        bant = sessions[0].metadata["bant"]
        assert bant.get("budget") == "50k"
        assert bant.get("need") == "SUV"

    def test_metadata_populated(self):
        rows = _make_successful_call()
        sessions = map_to_sessions(rows)
        meta = sessions[0].metadata
        assert "bant" in meta
        assert "duration_seconds" in meta
        assert "call_status" in meta
        assert meta["bant_complete"] is True

    def test_unknown_event_type(self):
        rows = [_make_row(event_type="weird_event")]
        sessions = map_to_sessions(rows)
        assert sessions[0].events[0].event_type == "unknown"

    def test_missing_session_id_generates_uuid(self):
        row = _make_row()
        del row[COL_SESSION_ID]
        sessions = map_to_sessions([row])
        assert len(sessions) == 1
        assert len(sessions[0].session_id) > 0

    def test_default_actor_assignment(self):
        """When actor column is absent, default actor should be assigned by event type."""
        rows = [_make_row(event_type="greeting")]
        sessions = map_to_sessions(rows)
        assert sessions[0].events[0].actor == "ai"

    def test_explicit_actor_preserved(self):
        rows = [_make_row(event_type="greeting", actor="customer")]
        sessions = map_to_sessions(rows)
        assert sessions[0].events[0].actor == "customer"


# ---------------------------------------------------------------------------
# Tests: compute_daily_metrics
# ---------------------------------------------------------------------------
class TestComputeDailyMetrics:
    def test_empty_sessions(self):
        metrics = compute_daily_metrics([])
        assert metrics.total_calls == 0
        assert metrics.connection_rate == 0.0
        assert metrics.date == ""

    def test_single_successful_session(self):
        rows = _make_successful_call()
        sessions = map_to_sessions(rows)
        metrics = compute_daily_metrics(sessions)

        assert metrics.total_calls == 1
        assert metrics.connected_calls == 1
        assert metrics.connection_rate == 100.0
        assert metrics.bant_completion_rate == 100.0
        assert metrics.transfer_rate == 100.0
        assert len(metrics.success_sessions) == 1
        assert len(metrics.failure_sessions) == 0

    def test_single_failed_session(self):
        rows = _make_failed_call()
        sessions = map_to_sessions(rows)
        metrics = compute_daily_metrics(sessions)

        assert metrics.total_calls == 1
        assert metrics.connected_calls == 0
        assert metrics.connection_rate == 0.0
        assert len(metrics.success_sessions) == 0
        assert len(metrics.failure_sessions) == 1

    def test_mixed_sessions(self):
        rows = _make_successful_call("ok1") + _make_failed_call("fail1") + _make_failed_call("fail2")
        sessions = map_to_sessions(rows)
        metrics = compute_daily_metrics(sessions)

        assert metrics.total_calls == 3
        assert metrics.connected_calls == 1
        assert 33.0 <= metrics.connection_rate <= 34.0
        assert len(metrics.success_sessions) == 1
        assert len(metrics.failure_sessions) == 2

    def test_date_extracted(self):
        rows = _make_successful_call()
        sessions = map_to_sessions(rows)
        metrics = compute_daily_metrics(sessions)
        assert metrics.date == "2026-03-24"

    def test_avg_duration(self):
        rows = _make_successful_call()
        sessions = map_to_sessions(rows)
        metrics = compute_daily_metrics(sessions)
        assert metrics.avg_duration_seconds > 0

    def test_anomaly_low_connection_rate(self):
        """Generate many failed calls to trigger low connection rate anomaly."""
        rows = _make_successful_call("ok1")
        for i in range(10):
            rows += _make_failed_call(f"fail-{i}")
        sessions = map_to_sessions(rows)
        metrics = compute_daily_metrics(sessions)

        anomaly_texts = " ".join(metrics.anomalies)
        assert "connection rate" in anomaly_texts.lower()

    def test_anomaly_unknown_event_types(self):
        rows = [_make_row(event_type="bizarre_event")]
        sessions = map_to_sessions(rows)
        metrics = compute_daily_metrics(sessions)
        assert any("unrecognized event" in a for a in metrics.anomalies)

    def test_rates_are_rounded(self):
        rows = _make_successful_call("ok1") + _make_failed_call("fail1") + _make_failed_call("fail2")
        sessions = map_to_sessions(rows)
        metrics = compute_daily_metrics(sessions)
        # Verify rates are rounded to 2 decimal places.
        assert metrics.connection_rate == round(metrics.connection_rate, 2)
        assert metrics.bant_completion_rate == round(metrics.bant_completion_rate, 2)
        assert metrics.transfer_rate == round(metrics.transfer_rate, 2)


# ---------------------------------------------------------------------------
# Tests: edge cases
# ---------------------------------------------------------------------------
class TestEdgeCases:
    def test_missing_timestamp_uses_fallback(self):
        row = _make_row()
        del row[COL_TIMESTAMP]
        sessions = map_to_sessions([row])
        assert len(sessions) == 1
        # Should not crash; uses utcnow fallback.
        assert isinstance(sessions[0].start_time, datetime)

    def test_missing_all_optional_fields(self):
        """Minimal row with just session_id, event_type, timestamp."""
        row = {
            COL_SESSION_ID: "minimal",
            COL_EVENT_TYPE: "call_queued",
            COL_TIMESTAMP: "2026-03-24T10:00:00Z",
        }
        sessions = map_to_sessions([row])
        assert len(sessions) == 1
        metrics = compute_daily_metrics(sessions)
        assert metrics.total_calls == 1

    def test_large_volume(self):
        """Ensure no crash with many sessions."""
        rows = []
        for i in range(100):
            rows += _make_failed_call(f"sess-{i:04d}", base_time=f"2026-03-24T{10 + i % 12}:{i % 60:02d}:")
        sessions = map_to_sessions(rows)
        metrics = compute_daily_metrics(sessions)
        assert metrics.total_calls == 100

    def test_duplicate_session_ids_merged(self):
        """Rows with the same session ID should merge into one session."""
        rows = [
            _make_row(session_id="dup", event_type="call_queued", timestamp="2026-03-24T10:00:00Z"),
            _make_row(session_id="dup", event_type="call_ended", timestamp="2026-03-24T10:05:00Z"),
        ]
        sessions = map_to_sessions(rows)
        assert len(sessions) == 1
        assert len(sessions[0].events) == 2
