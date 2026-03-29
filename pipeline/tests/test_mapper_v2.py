"""Unit tests for the v2 mapper module (3-table JOIN structure)."""

import pytest
from datetime import datetime, timezone

from mapper import (
    CallRecord,
    DailyMetrics,
    QualificationDepth,
    SegmentStats,
    map_to_call_records,
    compute_daily_metrics,
    _is_collected,
    _compute_segments,
    _detect_anomalies,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _make_row(
    call_id: str = "call-001",
    call_created_at: str = "2026-03-28T14:30:00Z",
    call_status: str = "completed",
    call_duration: int = 180,
    call_ended_by: str = "user",
    scenario_version: str = "v2.1",
    variant: str = "A",
    channel: str = "web",
    model_of_interest: str = "Tucson",
    first_name: str = "John",
    last_name: str = "Doe",
    first_dealer_id: str = "dealer-101",
    first_dealer_name: str = "Seoul Hyundai",
    script_en: str = "Hello, I am calling about...",
    summary: str = "Customer interested in Tucson.",
    voicemail: bool = False,
    hung_up: bool = False,
    call_type: str = "accepted",
    trim: str = "SEL Premium",
    dealer_consent: str = "yes",
    timeframe: str = "this month",
    payment_method: str = "finance",
    trade_in: str = "2019 Sonata",
    test_drive_interest: str = "yes",
    test_drive_slot: str = "2026-03-30 10:00",
    preferred_contact_channel: str = "phone",
    recommendation: str = "Tucson SEL Premium",
    lead_version: str = "v1",
    failed_message: str = "",
    **overrides,
) -> dict:
    """Build a mock BQ row matching the 3-table JOIN output."""
    row = {
        "call_id": call_id,
        "call_created_at": call_created_at,
        "call_status": call_status,
        "call_duration": call_duration,
        "call_ended_by": call_ended_by,
        "scenario_version": scenario_version,
        "variant": variant,
        "channel": channel,
        "model_of_interest": model_of_interest,
        "first_name": first_name,
        "last_name": last_name,
        "first_dealer_id": first_dealer_id,
        "first_dealer_name": first_dealer_name,
        "script_en": script_en,
        "summary": summary,
        "voicemail": voicemail,
        "hung_up": hung_up,
        "call_type": call_type,
        "trim": trim,
        "dealer_consent": dealer_consent,
        "timeframe": timeframe,
        "payment_method": payment_method,
        "trade_in": trade_in,
        "test_drive_interest": test_drive_interest,
        "test_drive_slot": test_drive_slot,
        "preferred_contact_channel": preferred_contact_channel,
        "recommendation": recommendation,
        "lead_version": lead_version,
        "failed_message": failed_message,
    }
    row.update(overrides)
    return row


def _make_voicemail_row(call_id: str = "call-vm-001") -> dict:
    return _make_row(
        call_id=call_id,
        voicemail=True,
        hung_up=False,
        call_type="voicemail",
        call_duration=15,
        call_ended_by="ai",
        trim="",
        dealer_consent="",
        timeframe="",
        payment_method="",
        trade_in="",
        test_drive_interest="",
        test_drive_slot="",
        preferred_contact_channel="",
    )


def _make_hungup_row(call_id: str = "call-hu-001") -> dict:
    return _make_row(
        call_id=call_id,
        voicemail=False,
        hung_up=True,
        call_type="hung_up",
        call_duration=8,
        call_ended_by="user",
        trim="",
        dealer_consent="",
        timeframe="",
        payment_method="",
        trade_in="",
        test_drive_interest="",
        test_drive_slot="",
        preferred_contact_channel="",
    )


def _make_accepted_no_qual_row(call_id: str = "call-nq-001") -> dict:
    """Accepted call but with no qualification fields collected."""
    return _make_row(
        call_id=call_id,
        call_type="accepted",
        voicemail=False,
        hung_up=False,
        dealer_consent="no",
        timeframe="not informed",
        payment_method="",
        trade_in="none",
        test_drive_slot="",
    )


# ---------------------------------------------------------------------------
# Tests: _is_collected helper
# ---------------------------------------------------------------------------
class TestIsCollected:
    def test_none_is_not_collected(self):
        assert _is_collected(None) is False

    def test_empty_string_is_not_collected(self):
        assert _is_collected("") is False

    def test_not_informed_is_not_collected(self):
        assert _is_collected("not informed") is False
        assert _is_collected("Not Informed") is False
        assert _is_collected("  NOT INFORMED  ") is False

    def test_nao_informado_is_not_collected(self):
        assert _is_collected("não informado") is False

    def test_bracket_variants_not_collected(self):
        assert _is_collected("[not informed]") is False
        assert _is_collected("[não informado]") is False
        assert _is_collected("[]") is False

    def test_none_string_not_collected(self):
        assert _is_collected("none") is False
        assert _is_collected("None") is False
        assert _is_collected("null") is False

    def test_real_value_is_collected(self):
        assert _is_collected("finance") is True
        assert _is_collected("2026-03-30 10:00") is True
        assert _is_collected("yes") is True
        assert _is_collected("Tucson") is True

    def test_numeric_value_is_collected(self):
        assert _is_collected(42) is True
        assert _is_collected(0) is True  # "0" is not in _EMPTY_VALUES


# ---------------------------------------------------------------------------
# Tests: map_to_call_records
# ---------------------------------------------------------------------------
class TestMapToCallRecords:
    def test_empty_input(self):
        assert map_to_call_records([]) == []

    def test_single_row(self):
        rows = [_make_row()]
        records = map_to_call_records(rows)
        assert len(records) == 1
        r = records[0]
        assert r.call_id == "call-001"
        assert r.call_status == "completed"
        assert r.call_duration == 180
        assert r.voicemail is False
        assert r.hung_up is False
        assert r.call_type == "accepted"
        assert r.model_of_interest == "Tucson"
        assert r.first_dealer_name == "Seoul Hyundai"

    def test_timestamp_parsing_iso(self):
        rows = [_make_row(call_created_at="2026-03-28T14:30:00Z")]
        records = map_to_call_records(rows)
        assert records[0].call_created_at is not None
        assert records[0].call_created_at.year == 2026
        assert records[0].call_created_at.month == 3
        assert records[0].call_created_at.day == 28

    def test_timestamp_parsing_datetime_passthrough(self):
        dt = datetime(2026, 3, 28, 14, 30, 0)
        rows = [_make_row(call_created_at=dt)]
        records = map_to_call_records(rows)
        assert records[0].call_created_at == dt

    def test_timestamp_invalid_becomes_none(self):
        rows = [_make_row(call_created_at="not-a-date")]
        records = map_to_call_records(rows)
        assert records[0].call_created_at is None

    def test_missing_fields_get_defaults(self):
        rows = [{"call_id": "minimal"}]
        records = map_to_call_records(rows)
        r = records[0]
        assert r.call_id == "minimal"
        assert r.call_duration == 0
        assert r.voicemail is False
        assert r.call_type == ""
        assert r.first_name == ""

    def test_multiple_rows(self):
        rows = [
            _make_row(call_id="c1"),
            _make_voicemail_row(call_id="c2"),
            _make_hungup_row(call_id="c3"),
        ]
        records = map_to_call_records(rows)
        assert len(records) == 3
        ids = {r.call_id for r in records}
        assert ids == {"c1", "c2", "c3"}

    def test_customer_name_property(self):
        rows = [_make_row(first_name="Jane", last_name="Smith")]
        records = map_to_call_records(rows)
        assert records[0].customer_name == "Jane Smith"

    def test_customer_name_missing_last(self):
        rows = [_make_row(first_name="Jane", last_name="")]
        records = map_to_call_records(rows)
        assert records[0].customer_name == "Jane"


# ---------------------------------------------------------------------------
# Tests: CallRecord properties
# ---------------------------------------------------------------------------
class TestCallRecordProperties:
    def test_is_connected_normal_call(self):
        rows = [_make_row(voicemail=False, hung_up=False)]
        r = map_to_call_records(rows)[0]
        assert r.is_connected is True

    def test_is_connected_voicemail(self):
        rows = [_make_voicemail_row()]
        r = map_to_call_records(rows)[0]
        assert r.is_connected is False

    def test_is_connected_hungup(self):
        rows = [_make_hungup_row()]
        r = map_to_call_records(rows)[0]
        assert r.is_connected is False

    def test_is_accepted(self):
        rows = [_make_row(call_type="accepted")]
        r = map_to_call_records(rows)[0]
        assert r.is_accepted is True

    def test_is_not_accepted(self):
        rows = [_make_row(call_type="voicemail")]
        r = map_to_call_records(rows)[0]
        assert r.is_accepted is False

    def test_is_qualified_with_all_key_fields(self):
        rows = [_make_row(timeframe="this month", payment_method="cash", trade_in="Sonata")]
        r = map_to_call_records(rows)[0]
        assert r.is_qualified is True

    def test_is_qualified_with_two_key_fields(self):
        rows = [_make_row(timeframe="this month", payment_method="cash", trade_in="")]
        r = map_to_call_records(rows)[0]
        assert r.is_qualified is True

    def test_is_not_qualified_with_one_key_field(self):
        rows = [_make_row(timeframe="this month", payment_method="", trade_in="")]
        r = map_to_call_records(rows)[0]
        assert r.is_qualified is False

    def test_is_not_qualified_with_not_informed(self):
        rows = [_make_row(timeframe="not informed", payment_method="not informed", trade_in="not informed")]
        r = map_to_call_records(rows)[0]
        assert r.is_qualified is False

    def test_has_dealer_consent_yes(self):
        rows = [_make_row(dealer_consent="yes")]
        r = map_to_call_records(rows)[0]
        assert r.has_dealer_consent is True

    def test_has_dealer_consent_no(self):
        rows = [_make_row(dealer_consent="no")]
        r = map_to_call_records(rows)[0]
        assert r.has_dealer_consent is False

    def test_has_test_drive_with_slot(self):
        rows = [_make_row(test_drive_slot="2026-03-30 10:00")]
        r = map_to_call_records(rows)[0]
        assert r.has_test_drive is True

    def test_has_test_drive_without_slot(self):
        rows = [_make_row(test_drive_slot="")]
        r = map_to_call_records(rows)[0]
        assert r.has_test_drive is False


# ---------------------------------------------------------------------------
# Tests: compute_daily_metrics funnel
# ---------------------------------------------------------------------------
class TestComputeDailyMetrics:
    def test_empty_records(self):
        m = compute_daily_metrics([])
        assert m.date == ""
        assert m.total_calls == 0

    def test_date_extracted(self):
        records = map_to_call_records([_make_row()])
        m = compute_daily_metrics(records)
        assert m.date == "2026-03-28"

    def test_single_accepted_call(self):
        records = map_to_call_records([_make_row()])
        m = compute_daily_metrics(records)
        assert m.total_calls == 1
        assert m.connected_count == 1
        assert m.accepted_count == 1
        assert m.voicemail_count == 0
        assert m.hungup_count == 0
        assert m.connected_rate == 100.0
        assert m.accepted_rate == 100.0

    def test_voicemail_counts(self):
        rows = [_make_voicemail_row(f"vm-{i}") for i in range(3)]
        records = map_to_call_records(rows)
        m = compute_daily_metrics(records)
        assert m.voicemail_count == 3
        assert m.connected_count == 0
        assert m.voicemail_rate == 100.0

    def test_hungup_not_double_counted_with_voicemail(self):
        """A voicemail call should not also count as hung_up in metrics."""
        rows = [_make_row(voicemail=True, hung_up=True, call_type="voicemail")]
        records = map_to_call_records(rows)
        m = compute_daily_metrics(records)
        assert m.voicemail_count == 1
        assert m.hungup_count == 0  # excluded because voicemail

    def test_mixed_funnel(self):
        rows = [
            _make_row(call_id="c1"),                    # accepted, connected, qualified
            _make_row(call_id="c2"),                    # accepted, connected, qualified
            _make_voicemail_row(call_id="c3"),          # voicemail
            _make_hungup_row(call_id="c4"),             # hung up
            _make_accepted_no_qual_row(call_id="c5"),   # accepted but not qualified
        ]
        records = map_to_call_records(rows)
        m = compute_daily_metrics(records)

        assert m.total_calls == 5
        assert m.voicemail_count == 1
        assert m.hungup_count == 1
        assert m.connected_count == 3  # c1, c2, c5 (not voicemail, not hungup)
        assert m.accepted_count == 3   # c1, c2, c5
        assert m.qualified_count == 2  # c1, c2

    def test_funnel_rates(self):
        rows = [
            _make_row(call_id="c1"),
            _make_voicemail_row(call_id="c2"),
            _make_hungup_row(call_id="c3"),
            _make_hungup_row(call_id="c4"),
        ]
        records = map_to_call_records(rows)
        m = compute_daily_metrics(records)

        assert m.total_calls == 4
        assert m.voicemail_rate == 25.0        # 1/4
        assert m.hungup_rate == 50.0           # 2/4
        assert m.connected_rate == 25.0        # 1/4
        assert m.accepted_rate == 100.0        # 1/1 connected
        assert m.qualified_rate == 100.0       # 1/1 accepted

    def test_duration_averages(self):
        rows = [
            _make_row(call_id="c1", call_duration=100),
            _make_row(call_id="c2", call_duration=200),
        ]
        records = map_to_call_records(rows)
        m = compute_daily_metrics(records)
        assert m.avg_duration_all == 150.0
        assert m.avg_duration_accepted == 150.0

    def test_voicemail_duration_average(self):
        rows = [
            _make_voicemail_row("vm1"),
            _make_row(call_id="c1", call_duration=200),
        ]
        # Override voicemail duration
        rows[0]["call_duration"] = 20
        records = map_to_call_records(rows)
        m = compute_daily_metrics(records)
        assert m.avg_duration_voicemail == 20.0

    def test_ended_by_rates(self):
        rows = [
            _make_row(call_id="c1", call_ended_by="user"),
            _make_row(call_id="c2", call_ended_by="customer"),
            _make_row(call_id="c3", call_ended_by="ai"),
            _make_row(call_id="c4", call_ended_by="assistant"),
        ]
        records = map_to_call_records(rows)
        m = compute_daily_metrics(records)
        assert m.ended_customer_rate == 50.0  # user + customer
        assert m.ended_ai_rate == 50.0        # ai + assistant

    def test_qualification_depth(self):
        rows = [
            _make_row(call_id="c1", call_type="accepted",
                      model_of_interest="Tucson", trim="SEL",
                      timeframe="this month", payment_method="cash",
                      trade_in="Sonata", test_drive_interest="yes",
                      test_drive_slot="2026-03-30", preferred_contact_channel="phone"),
            _make_row(call_id="c2", call_type="accepted",
                      model_of_interest="Santa Fe", trim="",
                      timeframe="not informed", payment_method="",
                      trade_in="", test_drive_interest="",
                      test_drive_slot="", preferred_contact_channel=""),
        ]
        records = map_to_call_records(rows)
        m = compute_daily_metrics(records)
        q = m.qualification
        assert q.total_accepted == 2
        assert q.model_count == 2   # both have model
        assert q.trim_count == 1    # only c1
        assert q.timeframe_count == 1
        assert q.payment_count == 1
        assert q.tradein_count == 1
        assert q.testdrive_count == 1
        assert q.slot_count == 1
        assert q.channel_count == 1
        # Rates
        assert q.model_rate == 100.0
        assert q.trim_rate == 50.0

    def test_accepted_and_failed_call_lists(self):
        rows = [
            _make_row(call_id="c1", call_type="accepted"),
            _make_row(call_id="c2", call_type="voicemail"),
        ]
        records = map_to_call_records(rows)
        m = compute_daily_metrics(records)
        assert len(m.accepted_calls) == 1
        assert m.accepted_calls[0].call_id == "c1"
        assert len(m.failed_calls) == 1
        assert m.failed_calls[0].call_id == "c2"


# ---------------------------------------------------------------------------
# Tests: Segment computation
# ---------------------------------------------------------------------------
class TestSegments:
    def test_model_segments(self):
        rows = [
            _make_row(call_id="c1", model_of_interest="Tucson", call_type="accepted"),
            _make_row(call_id="c2", model_of_interest="Tucson", call_type="voicemail"),
            _make_row(call_id="c3", model_of_interest="Santa Fe", call_type="accepted"),
        ]
        records = map_to_call_records(rows)
        model_seg, _, _ = _compute_segments(records)

        assert "Tucson" in model_seg
        assert "Santa Fe" in model_seg
        assert model_seg["Tucson"].calls == 2
        assert model_seg["Tucson"].accepted == 1
        assert model_seg["Santa Fe"].calls == 1
        assert model_seg["Santa Fe"].accepted == 1

    def test_dealer_segments(self):
        rows = [
            _make_row(call_id="c1", first_dealer_name="Seoul Hyundai", call_type="accepted",
                      dealer_consent="yes"),
            _make_row(call_id="c2", first_dealer_name="Seoul Hyundai", call_type="accepted",
                      dealer_consent="no"),
            _make_row(call_id="c3", first_dealer_name="Busan Motors", call_type="accepted",
                      dealer_consent="yes"),
        ]
        records = map_to_call_records(rows)
        _, dealer_seg, _ = _compute_segments(records)

        assert dealer_seg["Seoul Hyundai"].calls == 2
        assert dealer_seg["Seoul Hyundai"].consent == 1
        assert dealer_seg["Busan Motors"].consent == 1

    def test_channel_segments(self):
        rows = [
            _make_row(call_id="c1", channel="web"),
            _make_row(call_id="c2", channel="web"),
            _make_row(call_id="c3", channel="phone"),
        ]
        records = map_to_call_records(rows)
        _, _, channel_seg = _compute_segments(records)

        assert channel_seg["web"].calls == 2
        assert channel_seg["phone"].calls == 1

    def test_segment_rates(self):
        stats = SegmentStats(calls=10, accepted=8, qualified=4, consent=6, testdrive=2)
        assert stats.acceptance_rate == 80.0
        assert stats.qualification_rate == 50.0
        assert stats.consent_rate == 75.0

    def test_segment_rates_zero_division(self):
        stats = SegmentStats(calls=0, accepted=0)
        assert stats.acceptance_rate == 0.0
        assert stats.qualification_rate == 0.0

    def test_unknown_model_fallback(self):
        rows = [_make_row(call_id="c1", model_of_interest="")]
        records = map_to_call_records(rows)
        model_seg, _, _ = _compute_segments(records)
        assert "Unknown" in model_seg

    def test_segments_in_daily_metrics(self):
        rows = [
            _make_row(call_id="c1", model_of_interest="Tucson", channel="web"),
            _make_row(call_id="c2", model_of_interest="Santa Fe", channel="phone"),
        ]
        records = map_to_call_records(rows)
        m = compute_daily_metrics(records)
        assert "Tucson" in m.model_segments
        assert "Santa Fe" in m.model_segments
        assert "web" in m.channel_segments
        assert "phone" in m.channel_segments


# ---------------------------------------------------------------------------
# Tests: Anomaly detection
# ---------------------------------------------------------------------------
class TestAnomalyDetection:
    def test_high_voicemail_rate_anomaly(self):
        # 4 voicemails out of 5 calls = 80% > 35% threshold
        rows = [_make_voicemail_row(f"vm-{i}") for i in range(4)]
        rows.append(_make_row(call_id="c1"))
        records = map_to_call_records(rows)
        m = compute_daily_metrics(records)
        assert any("Voicemail Rate" in a for a in m.anomalies)

    def test_no_voicemail_anomaly_below_threshold(self):
        # 1 voicemail out of 10 calls = 10% < 35%
        rows = [_make_row(call_id=f"c{i}") for i in range(9)]
        rows.append(_make_voicemail_row("vm-1"))
        records = map_to_call_records(rows)
        m = compute_daily_metrics(records)
        assert not any("Voicemail Rate" in a for a in m.anomalies)

    def test_low_acceptance_rate_anomaly(self):
        # 1 accepted out of 10 connected = 10% < 30%
        rows = [_make_row(call_id=f"c{i}", call_type="rejected") for i in range(9)]
        rows.append(_make_row(call_id="c-ok", call_type="accepted"))
        records = map_to_call_records(rows)
        m = compute_daily_metrics(records)
        assert any("Acceptance Rate" in a for a in m.anomalies)

    def test_low_qualification_rate_anomaly(self):
        # 6+ accepted, but 0 qualified
        rows = [_make_accepted_no_qual_row(f"c{i}") for i in range(6)]
        records = map_to_call_records(rows)
        m = compute_daily_metrics(records)
        assert any("Qualification Rate" in a for a in m.anomalies)

    def test_short_duration_anomaly(self):
        rows = [_make_row(call_id=f"c{i}", call_duration=5) for i in range(3)]
        records = map_to_call_records(rows)
        m = compute_daily_metrics(records)
        assert any("평균 통화 시간" in a for a in m.anomalies)

    def test_dealer_zero_consent_anomaly(self):
        # 3+ accepted calls from one dealer with 0 consent
        rows = [
            _make_row(call_id=f"c{i}", first_dealer_name="Bad Dealer",
                      call_type="accepted", dealer_consent="no")
            for i in range(3)
        ]
        records = map_to_call_records(rows)
        m = compute_daily_metrics(records)
        assert any("Bad Dealer" in a and "Consent Rate 0%" in a for a in m.anomalies)

    def test_no_anomalies_on_healthy_data(self):
        rows = [_make_row(call_id=f"c{i}") for i in range(10)]
        records = map_to_call_records(rows)
        m = compute_daily_metrics(records)
        # All accepted, qualified, consent=yes, good duration -- should be clean
        assert len(m.anomalies) == 0


# ---------------------------------------------------------------------------
# Tests: QualificationDepth
# ---------------------------------------------------------------------------
class TestQualificationDepth:
    def test_rate_with_zero_accepted(self):
        q = QualificationDepth(total_accepted=0, model_count=5)
        assert q.model_rate == 0.0

    def test_rates_computed(self):
        q = QualificationDepth(
            total_accepted=10,
            model_count=8,
            trim_count=5,
            timeframe_count=7,
            payment_count=3,
            tradein_count=4,
            testdrive_count=6,
            slot_count=2,
            channel_count=9,
        )
        assert q.model_rate == 80.0
        assert q.trim_rate == 50.0
        assert q.timeframe_rate == 70.0
        assert q.payment_rate == 30.0
        assert q.tradein_rate == 40.0
        assert q.testdrive_rate == 60.0
        assert q.slot_rate == 20.0
        assert q.channel_rate == 90.0


# ---------------------------------------------------------------------------
# Tests: Edge cases
# ---------------------------------------------------------------------------
class TestEdgeCases:
    def test_large_volume(self):
        rows = [_make_row(call_id=f"c{i}") for i in range(200)]
        records = map_to_call_records(rows)
        m = compute_daily_metrics(records)
        assert m.total_calls == 200

    def test_all_none_fields(self):
        row = {k: None for k in [
            "call_id", "call_created_at", "call_status", "call_duration",
            "call_ended_by", "scenario_version", "channel", "model_of_interest",
            "first_name", "last_name", "first_dealer_id", "first_dealer_name",
            "script_en", "summary", "voicemail", "hung_up", "call_type",
            "trim", "dealer_consent", "timeframe", "payment_method", "trade_in",
            "test_drive_interest", "test_drive_slot", "preferred_contact_channel",
            "recommendation", "lead_version", "failed_message",
        ]}
        records = map_to_call_records([row])
        assert len(records) == 1
        r = records[0]
        assert r.call_id == ""
        assert r.call_duration == 0
        assert r.voicemail is False

    def test_zero_duration_excluded_from_avg(self):
        rows = [
            _make_row(call_id="c1", call_duration=0),
            _make_row(call_id="c2", call_duration=100),
        ]
        records = map_to_call_records(rows)
        m = compute_daily_metrics(records)
        assert m.avg_duration_all == 100.0  # only c2 counted
