from __future__ import annotations


CYCLING_DISCIPLINES = (
    "road",
    "gravel",
    "mtb",
)

DEVICE_CATEGORIES = (
    "power_meter",
    "heart_rate_sensor",
    "trainer",
    "recording_device",
    "temperature_sensor",
    "cadence_sensor",
    "speed_sensor",
    "other_sensor",
)

DEVICE_MOBILITY = (
    "fixed",
    "movable",
    "shared",
)

BIKE_DEVICE_ROLES = {
    "power_source": {
        "power_meter",
    },
    "cadence_source": {
        "power_meter",
        "cadence_sensor",
    },
    "speed_source": {
        "speed_sensor",
    },
}


def _normalize(
    value: str,
) -> str:
    return (
        value.strip()
        .lower()
        .replace("-", "_")
        .replace(" ", "_")
    )


def normalize_cycling_discipline(
    value: str,
) -> str:
    normalized = _normalize(value)

    aliases = {
        "road": "road",
        "road_bike": "road",
        "szosa": "road",
        "gravel": "gravel",
        "gravel_bike": "gravel",
        "mtb": "mtb",
        "mountain_bike": "mtb",
        "mountainbike": "mtb",
    }

    result = aliases.get(normalized)

    if result is None:
        raise ValueError(
            "Unsupported cycling discipline"
        )

    return result


def normalize_device_category(
    value: str,
) -> str:
    normalized = _normalize(value)

    if normalized not in DEVICE_CATEGORIES:
        raise ValueError(
            "Unsupported device category"
        )

    return normalized


def normalize_device_mobility(
    value: str,
) -> str:
    normalized = _normalize(value)

    if normalized not in DEVICE_MOBILITY:
        raise ValueError(
            "Unsupported device mobility"
        )

    return normalized


def normalize_bike_device_role(
    value: str,
) -> str:
    normalized = _normalize(value)

    if normalized not in BIKE_DEVICE_ROLES:
        raise ValueError(
            "Unsupported bike device role"
        )

    return normalized


def validate_role_category(
    *,
    role: str,
    category: str,
) -> None:
    if category not in BIKE_DEVICE_ROLES[role]:
        raise ValueError(
            (
                f"Device category {category} "
                f"cannot be used as {role}"
            )
        )


TRAINING_ENVIRONMENTS = (
    "indoor",
    "outdoor",
)

TRAINING_SETUP_DEVICE_ROLES = {
    "trainer": {
        "trainer",
    },
    "primary_power_source": {
        "power_meter",
        "trainer",
    },
    "secondary_power_source": {
        "power_meter",
        "trainer",
    },
    "hr_source": {
        "heart_rate_sensor",
    },
    "recording_device": {
        "recording_device",
    },
    "temperature_source": {
        "temperature_sensor",
    },
}


def normalize_training_environment(
    value: str,
) -> str:
    normalized = _normalize(value)

    if normalized not in TRAINING_ENVIRONMENTS:
        raise ValueError(
            "Unsupported training environment"
        )

    return normalized


def normalize_training_setup_role(
    value: str,
) -> str:
    normalized = _normalize(value)

    if normalized not in TRAINING_SETUP_DEVICE_ROLES:
        raise ValueError(
            "Unsupported training setup device role"
        )

    return normalized


def validate_training_setup_role_category(
    *,
    role: str,
    category: str,
) -> None:
    allowed = TRAINING_SETUP_DEVICE_ROLES[
        role
    ]

    if category not in allowed:
        raise ValueError(
            (
                f"Device category {category} "
                f"cannot be used as {role}"
            )
        )
