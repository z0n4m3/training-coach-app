from datetime import (
    datetime,
    timezone,
)

import pytest
from pydantic import ValidationError

from app.domain.cadence import (
    extract_cadence_targets,
    is_cadence_compliance_target,
    normalize_cadence_target,
)
from app.schemas.plan import (
    PlannedSessionCreate,
)


def base_plan(
    **overrides,
):
    data = {
        "planned_start_at":
            datetime(
                2026,
                10,
                12,
                16,
                0,
                tzinfo=timezone.utc,
            ),
        "name": "END",
        "sport": "cycling",
        "session_type": "END",
        "priority": "SUPPORT",
        "planned_duration_s": 5400,
        "targets": {
            "rpe": [2, 3],
        },
        "workout_structure": {
            "type": "steady",
        },
    }

    data.update(overrides)

    return data


def test_no_cadence_target_means_no_cadence_compliance():
    items = extract_cadence_targets(
        targets={
            "rpe": [2, 3],
        },
        workout_structure={
            "type": "steady",
        },
    )

    assert items == []


def test_self_selected_is_valid_and_not_compliance_target():
    target = {
        "mode": "self_selected",
    }

    normalized = normalize_cadence_target(
        target
    )

    assert normalized == {
        "mode": "self_selected",
    }

    assert (
        is_cadence_compliance_target(
            target
        )
        is False
    )


def test_low_cadence_interval_target_is_extracted():
    structure = {
        "type": "intervals",
        "steps": [
            {
                "type": "warmup",
                "duration_s": 900,
            },
            {
                "type": "work",
                "duration_s": 300,
                "targets": {
                    "cadence": {
                        "mode": "range",
                        "min_rpm": 55,
                        "max_rpm": 65,
                        "intent": "low_cadence",
                    }
                },
            },
        ],
    }

    items = extract_cadence_targets(
        targets={},
        workout_structure=structure,
    )

    assert len(items) == 1

    assert (
        items[0]["path"]
        == "workout_structure.steps[1].targets.cadence"
    )

    assert items[0]["target"] == {
        "mode": "range",
        "min_rpm": 55.0,
        "max_rpm": 65.0,
        "intent": "low_cadence",
    }

    assert (
        is_cadence_compliance_target(
            items[0]["target"]
        )
        is True
    )


def test_high_cadence_target_is_valid():
    target = {
        "mode": "range",
        "min_rpm": 105,
        "max_rpm": 120,
        "intent": "high_cadence",
    }

    normalized = normalize_cadence_target(
        target
    )

    assert (
        normalized["intent"]
        == "high_cadence"
    )


def test_intent_is_not_inferred_from_rpm():
    target = normalize_cadence_target(
        {
            "mode": "range",
            "min_rpm": 60,
            "max_rpm": 70,
            "intent": "custom",
        }
    )

    assert target["intent"] == "custom"


def test_invalid_cadence_range_is_rejected():
    with pytest.raises(
        ValueError,
        match="min_rpm",
    ):
        normalize_cadence_target(
            {
                "mode": "range",
                "min_rpm": 90,
                "max_rpm": 70,
                "intent": "low_cadence",
            }
        )


def test_self_selected_cannot_have_bounds():
    with pytest.raises(
        ValueError,
        match="cannot define rpm bounds",
    ):
        normalize_cadence_target(
            {
                "mode": "self_selected",
                "min_rpm": 80,
                "max_rpm": 90,
            }
        )


def test_plan_accepts_interval_cadence_target():
    payload = base_plan(
        workout_structure={
            "type": "intervals",
            "steps": [
                {
                    "type": "work",
                    "duration_s": 300,
                    "targets": {
                        "cadence": {
                            "mode": "range",
                            "min_rpm": 55,
                            "max_rpm": 65,
                            "intent": "low_cadence",
                        }
                    },
                }
            ],
        }
    )

    model = PlannedSessionCreate(
        **payload
    )

    assert (
        model.workout_structure[
            "steps"
        ][0][
            "targets"
        ][
            "cadence"
        ][
            "intent"
        ]
        == "low_cadence"
    )


def test_plan_rejects_invalid_cadence_target():
    payload = base_plan(
        targets={
            "cadence": {
                "mode": "range",
                "min_rpm": 110,
                "max_rpm": 100,
                "intent": "high_cadence",
            }
        }
    )

    with pytest.raises(
        ValidationError,
    ):
        PlannedSessionCreate(
            **payload
        )


def test_self_selected_cannot_define_intent():
    with pytest.raises(
        ValueError,
        match="cannot define rpm bounds or intent",
    ):
        normalize_cadence_target(
            {
                "mode": "self_selected",
                "intent": "low_cadence",
            }
        )
