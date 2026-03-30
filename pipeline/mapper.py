"""Data mapper: transforms merged BQ rows into call records and daily metrics.

Works with the 3-table JOIN output from bq_client (meta + analysis + lead).
"""

import logging
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

logger = logging.getLogger(__name__)

# Values treated as "not collected" in analysis fields.
_EMPTY_VALUES = frozenset({
    "", "not informed", "não informado", "[]",
    "[not informed]", "[não informado]", "none", "null",
})


def _is_collected(value: Any) -> bool:
    """Check if a qualification field has a meaningful value."""
    if value is None:
        return False
    v = str(value).strip().lower()
    return v not in _EMPTY_VALUES


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    return str(value).strip()


def _safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    if value is None:
        return default
    try:
        return float(value)
    except (ValueError, TypeError):
        return default


def _safe_bool(value: Any, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in ("true", "1", "yes")


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------
@dataclass
class CallRecord:
    """A single H-Voice call with merged data from meta + analysis + lead."""

    call_id: str

    # Call meta
    call_created_at: datetime | None
    call_status: str
    call_duration: float  # seconds
    call_ended_by: str
    scenario_version: str
    channel: str
    model_of_interest: str
    first_name: str
    last_name: str

    # Dealer
    first_dealer_id: str
    first_dealer_name: str

    # Transcript & summary
    script_en: str
    summary: str

    # Analysis
    voicemail: bool
    hung_up: bool
    call_type: str  # "accepted", etc.
    trim: str
    dealer_consent: str
    timeframe: str
    payment_method: str
    trade_in: str
    test_drive_interest: str
    test_drive_slot: str
    preferred_contact_channel: str
    recommendation: str

    # Lead
    lead_version: str
    failed_message: str

    @property
    def is_connected(self) -> bool:
        """Connected = not voicemail AND not early hang-up."""
        return not self.voicemail and not self.hung_up

    @property
    def is_accepted(self) -> bool:
        """Accepted = type is 'accepted'."""
        return self.call_type.lower() == "accepted"

    @property
    def is_dealer_assigned(self) -> bool:
        """Dealer Assigned = dealer_consent is 'yes'."""
        return _safe_str(self.dealer_consent).lower() == "yes"

    @property
    def bant_collected(self) -> int:
        """Count of BANT key fields collected (timeframe, payment, trade_in)."""
        key_fields = [self.timeframe, self.payment_method, self.trade_in]
        return sum(_is_collected(f) for f in key_fields)

    @property
    def is_ready_lead(self) -> bool:
        """Ready Lead = Dealer Assigned AND 2+ BANT fields collected."""
        return self.is_dealer_assigned and self.bant_collected >= 2

    @property
    def has_test_drive(self) -> bool:
        return _is_collected(self.test_drive_slot)

    @property
    def customer_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()


@dataclass
class QualificationDepth:
    """Counts of collected qualification fields across accepted calls."""

    model_count: int = 0
    trim_count: int = 0
    timeframe_count: int = 0
    payment_count: int = 0
    tradein_count: int = 0
    testdrive_count: int = 0
    slot_count: int = 0
    channel_count: int = 0
    total_accepted: int = 0

    def _rate(self, count: int) -> float:
        if self.total_accepted == 0:
            return 0.0
        return round(count / self.total_accepted * 100, 1)

    @property
    def model_rate(self) -> float:
        return self._rate(self.model_count)

    @property
    def trim_rate(self) -> float:
        return self._rate(self.trim_count)

    @property
    def timeframe_rate(self) -> float:
        return self._rate(self.timeframe_count)

    @property
    def payment_rate(self) -> float:
        return self._rate(self.payment_count)

    @property
    def tradein_rate(self) -> float:
        return self._rate(self.tradein_count)

    @property
    def testdrive_rate(self) -> float:
        return self._rate(self.testdrive_count)

    @property
    def slot_rate(self) -> float:
        return self._rate(self.slot_count)

    @property
    def channel_rate(self) -> float:
        return self._rate(self.channel_count)


@dataclass
class SegmentStats:
    """Per-segment (model/dealer/channel) aggregated stats."""

    calls: int = 0
    accepted: int = 0
    dealer_assigned: int = 0
    ready_lead: int = 0
    testdrive: int = 0

    @property
    def acceptance_rate(self) -> float:
        return round(self.accepted / self.calls * 100, 1) if self.calls else 0.0

    @property
    def dealer_assigned_rate(self) -> float:
        return round(self.dealer_assigned / self.accepted * 100, 1) if self.accepted else 0.0

    @property
    def ready_rate(self) -> float:
        return round(self.ready_lead / self.accepted * 100, 1) if self.accepted else 0.0


@dataclass
class DailyMetrics:
    """Aggregated daily metrics following the Call Funnel structure."""

    date: str

    # Funnel counts
    total_calls: int = 0
    voicemail_count: int = 0
    hungup_count: int = 0
    connected_count: int = 0
    accepted_count: int = 0
    dealer_assigned_count: int = 0
    testdrive_count: int = 0
    ready_lead_count: int = 0

    # Funnel rates (%)
    voicemail_rate: float = 0.0
    hungup_rate: float = 0.0
    connected_rate: float = 0.0
    accepted_rate: float = 0.0  # of connected
    dealer_assigned_rate: float = 0.0  # of accepted
    testdrive_rate: float = 0.0  # of accepted
    ready_lead_rate: float = 0.0  # of dealer_assigned

    # Call performance
    avg_duration_all: float = 0.0
    avg_duration_accepted: float = 0.0
    avg_duration_voicemail: float = 0.0
    ended_customer_rate: float = 0.0
    ended_ai_rate: float = 0.0

    # Qualification depth
    qualification: QualificationDepth = field(default_factory=QualificationDepth)

    # Segments
    model_segments: dict[str, SegmentStats] = field(default_factory=dict)
    dealer_segments: dict[str, SegmentStats] = field(default_factory=dict)
    channel_segments: dict[str, SegmentStats] = field(default_factory=dict)

    # Call lists
    accepted_calls: list[CallRecord] = field(default_factory=list)
    failed_calls: list[CallRecord] = field(default_factory=list)

    # Anomalies
    anomalies: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Mapping
# ---------------------------------------------------------------------------
def map_to_call_records(raw_rows: list[dict[str, Any]]) -> list[CallRecord]:
    """Convert raw BQ rows (3-table JOIN result) into CallRecord objects."""
    records: list[CallRecord] = []

    for row in raw_rows:
        ts = row.get("call_created_at")
        if isinstance(ts, str):
            try:
                ts = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            except ValueError:
                ts = None

        records.append(CallRecord(
            call_id=_safe_str(row.get("call_id")),
            call_created_at=ts,
            call_status=_safe_str(row.get("call_status")),
            call_duration=_safe_float(row.get("call_duration")),
            call_ended_by=_safe_str(row.get("call_ended_by")),
            scenario_version=_safe_str(row.get("scenario_version")),
            channel=_safe_str(row.get("channel")),
            model_of_interest=_safe_str(row.get("model_of_interest")),
            first_name=_safe_str(row.get("first_name")),
            last_name=_safe_str(row.get("last_name")),
            first_dealer_id=_safe_str(row.get("first_dealer_id")),
            first_dealer_name=_safe_str(row.get("first_dealer_name")),
            script_en=_safe_str(row.get("script_en")),
            summary=_safe_str(row.get("summary")),
            voicemail=_safe_bool(row.get("voicemail")),
            hung_up=_safe_bool(row.get("hung_up")),
            call_type=_safe_str(row.get("call_type")),
            trim=_safe_str(row.get("trim")),
            dealer_consent=_safe_str(row.get("dealer_consent")),
            timeframe=_safe_str(row.get("timeframe")),
            payment_method=_safe_str(row.get("payment_method")),
            trade_in=_safe_str(row.get("trade_in")),
            test_drive_interest=_safe_str(row.get("test_drive_interest")),
            test_drive_slot=_safe_str(row.get("test_drive_slot")),
            preferred_contact_channel=_safe_str(row.get("preferred_contact_channel")),
            recommendation=_safe_str(row.get("recommendation")),
            lead_version=_safe_str(row.get("lead_version")),
            failed_message=_safe_str(row.get("failed_message")),
        ))

    logger.info("Mapped %d rows into CallRecords", len(records))
    return records


def _compute_qualification(accepted: list[CallRecord]) -> QualificationDepth:
    """Compute qualification depth across accepted calls."""
    q = QualificationDepth(total_accepted=len(accepted))
    for c in accepted:
        if _is_collected(c.model_of_interest):
            q.model_count += 1
        if _is_collected(c.trim):
            q.trim_count += 1
        if _is_collected(c.timeframe):
            q.timeframe_count += 1
        if _is_collected(c.payment_method):
            q.payment_count += 1
        if _is_collected(c.trade_in):
            q.tradein_count += 1
        if _is_collected(c.test_drive_interest):
            q.testdrive_count += 1
        if _is_collected(c.test_drive_slot):
            q.slot_count += 1
        if _is_collected(c.preferred_contact_channel):
            q.channel_count += 1
    return q


def _compute_segments(
    records: list[CallRecord],
) -> tuple[dict[str, SegmentStats], dict[str, SegmentStats], dict[str, SegmentStats]]:
    """Compute model / dealer / channel segment stats."""
    models: dict[str, SegmentStats] = defaultdict(SegmentStats)
    dealers: dict[str, SegmentStats] = defaultdict(SegmentStats)
    channels: dict[str, SegmentStats] = defaultdict(SegmentStats)

    for c in records:
        for seg, key in [
            (models, c.model_of_interest or "Unknown"),
            (dealers, c.first_dealer_name or "Unknown"),
            (channels, c.channel or "Unknown"),
        ]:
            seg[key].calls += 1
            if c.is_accepted:
                seg[key].accepted += 1
            if c.is_dealer_assigned:
                seg[key].dealer_assigned += 1
            if c.is_ready_lead:
                seg[key].ready_lead += 1
            if c.has_test_drive:
                seg[key].testdrive += 1

    return dict(models), dict(dealers), dict(channels)


def _detect_anomalies(m: DailyMetrics) -> list[str]:
    """Detect anomalies in daily metrics."""
    anomalies: list[str] = []

    if m.total_calls > 0 and m.voicemail_rate > 35.0:
        anomalies.append(
            f"높은 Voicemail Rate: {m.voicemail_rate}% (기준 35% 초과)"
        )
    if m.connected_count > 0 and m.accepted_rate < 30.0:
        anomalies.append(
            f"낮은 Acceptance Rate: {m.accepted_rate}% (기준 30% 미만)"
        )
    if m.accepted_count > 5 and m.dealer_assigned_rate < 30.0:
        anomalies.append(
            f"낮은 Dealer Assigned Rate: {m.dealer_assigned_rate}% (기준 30% 미만)"
        )
    if m.avg_duration_all > 0 and m.avg_duration_all < 10.0:
        anomalies.append(
            f"비정상적으로 짧은 평균 통화 시간: {m.avg_duration_all}초"
        )

    # Check for dealers with 0% dealer assigned rate but 3+ accepted calls.
    for dealer, stats in m.dealer_segments.items():
        if stats.accepted >= 3 and stats.dealer_assigned_rate == 0.0:
            anomalies.append(
                f"딜러 '{dealer}' Dealer Assigned Rate 0% ({stats.accepted}건 중 0건)"
            )

    return anomalies


def compute_daily_metrics(records: list[CallRecord]) -> DailyMetrics:
    """Aggregate CallRecords into daily funnel metrics."""
    if not records:
        return DailyMetrics(date="")

    date_str = ""
    if records[0].call_created_at:
        date_str = records[0].call_created_at.strftime("%Y-%m-%d")

    total = len(records)
    voicemail = [c for c in records if c.voicemail]
    hungup = [c for c in records if c.hung_up and not c.voicemail]
    connected = [c for c in records if c.is_connected]
    accepted = [c for c in records if c.is_accepted]
    dealer_assigned = [c for c in records if c.is_dealer_assigned]
    testdrive = [c for c in records if c.has_test_drive]
    ready_leads = [c for c in records if c.is_ready_lead]

    # Rates
    def _pct(num: int, denom: int) -> float:
        return round(num / denom * 100, 1) if denom else 0.0

    # Durations
    all_durations = [c.call_duration for c in records if c.call_duration > 0]
    accepted_durations = [c.call_duration for c in accepted if c.call_duration > 0]
    vm_durations = [c.call_duration for c in voicemail if c.call_duration > 0]

    avg_all = round(sum(all_durations) / len(all_durations), 1) if all_durations else 0.0
    avg_accepted = round(sum(accepted_durations) / len(accepted_durations), 1) if accepted_durations else 0.0
    avg_vm = round(sum(vm_durations) / len(vm_durations), 1) if vm_durations else 0.0

    # Ended by
    ended_customer = sum(1 for c in records if c.call_ended_by.lower() in ("user", "customer"))
    ended_ai = sum(1 for c in records if c.call_ended_by.lower() in ("ai", "assistant", "bot"))

    # Qualification depth
    qualification = _compute_qualification(accepted)

    # Segments
    model_seg, dealer_seg, channel_seg = _compute_segments(records)

    m = DailyMetrics(
        date=date_str,
        total_calls=total,
        voicemail_count=len(voicemail),
        hungup_count=len(hungup),
        connected_count=len(connected),
        accepted_count=len(accepted),
        dealer_assigned_count=len(dealer_assigned),
        testdrive_count=len(testdrive),
        ready_lead_count=len(ready_leads),
        voicemail_rate=_pct(len(voicemail), total),
        hungup_rate=_pct(len(hungup), total),
        connected_rate=_pct(len(connected), total),
        accepted_rate=_pct(len(accepted), len(connected)),
        dealer_assigned_rate=_pct(len(dealer_assigned), len(accepted)),
        testdrive_rate=_pct(len(testdrive), len(accepted)),
        ready_lead_rate=_pct(len(ready_leads), len(dealer_assigned)),
        avg_duration_all=avg_all,
        avg_duration_accepted=avg_accepted,
        avg_duration_voicemail=avg_vm,
        ended_customer_rate=_pct(ended_customer, total),
        ended_ai_rate=_pct(ended_ai, total),
        qualification=qualification,
        model_segments=model_seg,
        dealer_segments=dealer_seg,
        channel_segments=channel_seg,
        accepted_calls=accepted,
        failed_calls=[c for c in records if not c.is_accepted],
        anomalies=[],
    )

    m.anomalies = _detect_anomalies(m)
    logger.info(
        "Metrics: total=%d, connected=%d(%.1f%%), accepted=%d(%.1f%%), "
        "dealer_assigned=%d(%.1f%%), ready_lead=%d(%.1f%%), testdrive=%d",
        m.total_calls, m.connected_count, m.connected_rate,
        m.accepted_count, m.accepted_rate,
        m.dealer_assigned_count, m.dealer_assigned_rate,
        m.ready_lead_count, m.ready_lead_rate,
        m.testdrive_count,
    )
    return m
