import json
from dataclasses import replace
from pathlib import Path

from app.services.canonicalizer import canonicalize
from app.services.intervals_mapper import from_intervals

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return from_intervals(json.loads((FIX / name).read_text()))


def test_field_level_merge_uses_garmin_hr_and_mywhoosh_distance():
    garmin = load("garmin.json")
    mywhoosh = load("mywhoosh.json")
    result = canonicalize([garmin, mywhoosh], source_preference="auto")

    assert result.duplicate_status == "merged"
    assert result.values["avg_hr_bpm"] == 144
    assert result.values["distance_m"] == 36250

    provenance = {m.metric_name: m.source_provider_activity_id for m in result.metrics}
    assert provenance["avg_hr_bpm"] == "garmin-001"
    assert provenance["distance_m"] == "mywhoosh-001"


def test_fingerprint_is_stable_when_second_source_arrives():
    garmin = load("garmin.json")
    mywhoosh = load("mywhoosh.json")
    single = canonicalize([garmin], source_preference="auto")
    merged = canonicalize([garmin, mywhoosh], source_preference="auto")
    assert single.fingerprint == merged.fingerprint


def test_primary_prefers_garmin_when_virtual_source_only_adds_route_metrics():
    garmin = replace(
        load("garmin.json"),
        recording_source="GARMIN_CONNECT",
    )
    mywhoosh = replace(
        load("mywhoosh.json"),
        recording_source="OAUTH_CLIENT",
        avg_hr_bpm=garmin.avg_hr_bpm,
        max_hr_bpm=garmin.max_hr_bpm,
    )

    result = canonicalize([garmin, mywhoosh], source_preference="auto")

    assert result.primary_provider_activity_id == "garmin-001"

    provenance = {
        m.metric_name: m.source_provider_activity_id
        for m in result.metrics
    }
    assert provenance["avg_hr_bpm"] == "garmin-001"
    assert provenance["distance_m"] == "mywhoosh-001"
