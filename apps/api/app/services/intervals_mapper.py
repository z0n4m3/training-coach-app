from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from app.domain.activity import ActivitySnapshot


def _first(d: dict[str, Any], keys: Iterable[str]):
    for key in keys:
        value = d.get(key)
        if value is not None:
            return value
    return None


def _float(value):
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _parse_dt(value: str | None) -> datetime:
    if not value:
        raise ValueError("Activity has no start timestamp")
    value = value.replace("Z", "+00:00")
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def _recording_source(payload: dict[str, Any]) -> str | None:
    direct = _first(payload, ["source", "source_name", "device_name", "device", "app_name"])
    if direct:
        return str(direct)
    external_id = str(payload.get("external_id") or "").lower()
    for token in ("garmin", "mywhoosh", "zwift", "wahoo"):
        if token in external_id:
            return token
    return None


def from_intervals(payload: dict[str, Any]) -> ActivitySnapshot:
    duration = _float(_first(payload, ["moving_time", "elapsed_time", "icu_duration", "duration"]))
    work_j = _float(_first(payload, ["icu_joules", "work", "joules"]))
    return ActivitySnapshot(
        provider_activity_id=str(payload["id"]),
        recording_source=_recording_source(payload),
        name=_first(payload, ["name", "title"]),
        sport=str(_first(payload, ["type", "sport", "activity_type"]) or "Unknown"),
        indoor=payload.get("trainer") if payload.get("trainer") is not None else payload.get("indoor"),
        start_at=_parse_dt(_first(payload, ["start_date", "start_date_local"])),
        duration_s=duration,
        distance_m=_float(_first(payload, ["distance", "icu_distance"])),
        elevation_m=_float(_first(payload, ["total_elevation_gain", "icu_elevation_gain", "elevation_gain"])),
        avg_power_w=_float(_first(payload, ["average_watts", "icu_average_watts", "avg_power"])),
        normalized_power_w=_float(_first(payload, ["weighted_average_watts", "icu_weighted_avg_watts", "normalized_power"])),
        avg_hr_bpm=_float(_first(payload, ["average_heartrate", "average_hr", "avg_hr"])),
        max_hr_bpm=_float(_first(payload, ["max_heartrate", "max_hr"])),
        avg_cadence_rpm=_float(_first(payload, ["average_cadence", "avg_cadence"])),
        work_kj=(work_j / 1000.0) if work_j and work_j > 10000 else work_j,
        training_load=_float(_first(payload, ["icu_training_load", "training_load", "load"])),
        paired_event_id=(str(payload["paired_event_id"]) if payload.get("paired_event_id") is not None else None),
        raw_payload=payload,
    )
