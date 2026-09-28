from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from hashlib import sha256
from typing import Any


@dataclass(slots=True)
class ActivitySnapshot:
    provider_activity_id: str
    recording_source: str | None
    name: str | None
    sport: str
    indoor: bool | None
    start_at: datetime
    duration_s: float | None = None
    distance_m: float | None = None
    elevation_m: float | None = None
    avg_power_w: float | None = None
    normalized_power_w: float | None = None
    avg_hr_bpm: float | None = None
    max_hr_bpm: float | None = None
    avg_cadence_rpm: float | None = None
    work_kj: float | None = None
    training_load: float | None = None
    paired_event_id: str | None = None
    raw_payload: dict[str, Any] | None = None

    @property
    def end_at(self) -> datetime | None:
        if self.duration_s is None:
            return None
        return self.start_at + timedelta(seconds=self.duration_s)

    @property
    def payload_hash(self) -> str:
        import json
        canonical = json.dumps(self.raw_payload or {}, sort_keys=True, separators=(",", ":"), default=str)
        return sha256(canonical.encode()).hexdigest()

    def fingerprint_component(self) -> str:
        rounded_start = self.start_at.astimezone(timezone.utc).replace(second=0, microsecond=0).isoformat()
        rounded_duration = int(round((self.duration_s or 0) / 60.0) * 60)
        return f"{self.sport}|{rounded_start}|{rounded_duration}"


@dataclass(slots=True)
class MetricChoice:
    metric_name: str
    value: float | str
    unit: str | None
    source_provider_activity_id: str
    quality_score: float
    reason: str
