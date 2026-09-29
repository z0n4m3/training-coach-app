from __future__ import annotations

from dataclasses import dataclass
from datetime import timezone
from hashlib import sha256
from statistics import median
from typing import Iterable

from app.domain.activity import ActivitySnapshot, MetricChoice


METRICS = {
    "duration_s": "s",
    "distance_m": "m",
    "elevation_m": "m",
    "avg_power_w": "W",
    "normalized_power_w": "W",
    "avg_hr_bpm": "bpm",
    "max_hr_bpm": "bpm",
    "avg_cadence_rpm": "rpm",
    "work_kj": "kJ",
    "training_load": None,
}

PHYSIOLOGY = {"avg_power_w", "normalized_power_w", "avg_hr_bpm", "max_hr_bpm", "avg_cadence_rpm", "work_kj", "training_load"}
VIRTUAL = {"distance_m", "elevation_m"}

PRIMARY_SIGNAL_METRICS = (
    "avg_power_w",
    "normalized_power_w",
    "avg_hr_bpm",
    "max_hr_bpm",
    "avg_cadence_rpm",
    "work_kj",
)


@dataclass(slots=True)
class CanonicalResult:
    fingerprint: str
    sport: str
    indoor: bool | None
    start_at: object
    end_at: object
    duplicate_status: str
    values: dict[str, float | None]
    metrics: list[MetricChoice]
    primary_provider_activity_id: str


def _source_bonus(source: str | None, metric: str, preference: str = "auto") -> float:
    s = (source or "unknown").lower()
    score = 0.0
    if preference != "auto" and preference.lower() in s:
        score += 0.20
    if preference == "auto":
        if metric in PHYSIOLOGY and "garmin" in s:
            score += 0.12
        if metric in VIRTUAL and any(x in s for x in ("mywhoosh", "zwift")):
            score += 0.06
    return score


def _completeness(activity: ActivitySnapshot) -> float:
    values = [getattr(activity, metric) for metric in METRICS]
    return sum(v is not None for v in values) / len(values)


def _metric_score(activity: ActivitySnapshot, metric: str, preference: str) -> float:
    if getattr(activity, metric) is None:
        return -1.0
    score = 0.65 + 0.20 * _completeness(activity) + _source_bonus(activity.recording_source, metric, preference)
    return min(1.0, score)


def _primary_rank(activity: ActivitySnapshot) -> tuple[int, int, float]:
    """Rank the source representing the training recording as a whole.

    Route/virtual metrics such as distance must not make a virtual platform
    the PRIMARY source when another recording contains equally rich
    physiological data. Metric-level provenance is still decided separately.
    """
    signal_count = sum(
        getattr(activity, metric) is not None
        for metric in PRIMARY_SIGNAL_METRICS
    )
    source = (activity.recording_source or "").lower()

    # Dedicated Garmin recording wins a tie in physiological richness.
    # This is only a tie-breaker; a genuinely richer source can still win.
    garmin_tiebreaker = 1 if "garmin" in source else 0

    return signal_count, garmin_tiebreaker, _completeness(activity)


def canonicalize(activities: Iterable[ActivitySnapshot], source_preference: str = "auto") -> CanonicalResult:
    items = list(activities)
    if not items:
        raise ValueError("At least one activity is required")

    primary = max(items, key=_primary_rank)
    metrics: list[MetricChoice] = []
    values: dict[str, float | None] = {}

    for metric, unit in METRICS.items():
        ranked = sorted(items, key=lambda a: _metric_score(a, metric, source_preference), reverse=True)
        chosen = ranked[0]
        value = getattr(chosen, metric)
        if value is None:
            values[metric] = None
            continue
        quality = _metric_score(chosen, metric, source_preference)
        values[metric] = float(value)
        metrics.append(
            MetricChoice(
                metric_name=metric,
                value=float(value),
                unit=unit,
                source_provider_activity_id=chosen.provider_activity_id,
                quality_score=quality,
                reason=f"best available metric; source={chosen.recording_source or 'unknown'}; preference={source_preference}",
            )
        )

    # Fingerprint describes the physical session, not the current set of source files.
    # This keeps the identity stable when a second recording arrives later.
    start_epoch = min(a.start_at for a in items).astimezone(timezone.utc).timestamp()
    start_bucket = int(start_epoch // 300) * 300  # 5-minute bucket
    durations = [a.duration_s for a in items if a.duration_s is not None]
    duration_bucket = int(round((median(durations) if durations else 0.0) / 300.0) * 300)
    indoor_flag = "i" if primary.indoor is True else "o" if primary.indoor is False else "u"
    fingerprint_raw = f"{primary.sport.lower()}|{indoor_flag}|{start_bucket}|{duration_bucket}"
    fingerprint = sha256(fingerprint_raw.encode()).hexdigest()
    end_at = max((a.end_at for a in items if a.end_at is not None), default=None)

    return CanonicalResult(
        fingerprint=fingerprint,
        sport=primary.sport,
        indoor=primary.indoor,
        start_at=min(a.start_at for a in items),
        end_at=end_at,
        duplicate_status="merged" if len(items) > 1 else "single",
        values=values,
        metrics=metrics,
        primary_provider_activity_id=primary.provider_activity_id,
    )
