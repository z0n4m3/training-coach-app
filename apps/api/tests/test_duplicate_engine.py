import json
from pathlib import Path

from app.services.duplicate_engine import score_duplicate, build_groups
from app.services.intervals_mapper import from_intervals

FIX = Path(__file__).parent / "fixtures"


def load(name):
    return from_intervals(json.loads((FIX / name).read_text()))


def test_garmin_mywhoosh_are_detected_as_duplicate():
    garmin = load("garmin.json")
    mywhoosh = load("mywhoosh.json")
    score = score_duplicate(garmin, mywhoosh)
    assert score.total >= 0.90
    assert build_groups([garmin, mywhoosh], 0.90) == [[0, 1]]


def test_separate_rides_are_not_merged():
    garmin = load("garmin.json")
    other = load("mywhoosh.json")
    other.start_at = other.start_at.replace(hour=20)
    assert score_duplicate(garmin, other).total < 0.90
    groups = sorted(build_groups([garmin, other], 0.90))
    assert groups == [[0], [1]]
