import json
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
