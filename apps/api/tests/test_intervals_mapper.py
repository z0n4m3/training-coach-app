import json
from pathlib import Path
from app.services.intervals_mapper import from_intervals

FIX = Path(__file__).parent / "fixtures"


def test_maps_common_intervals_fields():
    payload = json.loads((FIX / "garmin.json").read_text())
    a = from_intervals(payload)
    assert a.provider_activity_id == "garmin-001"
    assert a.recording_source == "Garmin"
    assert a.avg_power_w == 201
    assert a.avg_hr_bpm == 144
    assert a.work_kj == 844.2
