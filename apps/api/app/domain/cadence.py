from __future__ import annotations

from typing import Any, Iterator


CADENCE_MODES = {
    "self_selected",
    "range",
}

CADENCE_INTENTS = {
    "low_cadence",
    "high_cadence",
    "technique",
    "custom",
}

# Granice jakości danych, a nie zalecenia treningowe.
MIN_VALID_RPM = 20.0
MAX_VALID_RPM = 250.0


def _number(
    value: Any,
    *,
    field: str,
) -> float:
    if isinstance(value, bool):
        raise ValueError(
            f"{field} must be numeric"
        )

    try:
        return float(value)

    except (
        TypeError,
        ValueError,
    ) as exc:
        raise ValueError(
            f"{field} must be numeric"
        ) from exc


def normalize_cadence_target(
    raw: Any,
) -> dict:
    if not isinstance(raw, dict):
        raise ValueError(
            "cadence target must be an object"
        )

    mode = raw.get("mode")

    if mode not in CADENCE_MODES:
        raise ValueError(
            "cadence mode must be "
            "'self_selected' or 'range'"
        )

    if mode == "self_selected":
        if (
            "min_rpm" in raw
            or "max_rpm" in raw
        ):
            raise ValueError(
                "self_selected cadence "
                "cannot define rpm bounds"
            )

        return {
            "mode": "self_selected"
        }

    try:
        minimum_raw = raw["min_rpm"]
        maximum_raw = raw["max_rpm"]
    except KeyError as exc:
        raise ValueError(
            "range cadence requires "
            "min_rpm and max_rpm"
        ) from exc

    minimum = _number(
        minimum_raw,
        field="min_rpm",
    )

    maximum = _number(
        maximum_raw,
        field="max_rpm",
    )

    if (
        minimum < MIN_VALID_RPM
        or maximum > MAX_VALID_RPM
    ):
        raise ValueError(
            "cadence rpm bounds are "
            "outside plausible range"
        )

    if minimum > maximum:
        raise ValueError(
            "min_rpm must be <= max_rpm"
        )

    intent = raw.get("intent")

    if intent not in CADENCE_INTENTS:
        raise ValueError(
            "range cadence requires intent: "
            "low_cadence, high_cadence, "
            "technique or custom"
        )

    return {
        "mode": "range",
        "min_rpm": round(minimum, 2),
        "max_rpm": round(maximum, 2),
        "intent": intent,
    }


def is_cadence_compliance_target(
    raw: Any,
) -> bool:
    target = normalize_cadence_target(
        raw
    )

    return (
        target["mode"]
        == "range"
    )


def _walk_structure(
    node: Any,
    *,
    path: str,
) -> Iterator[tuple[str, Any]]:
    if isinstance(node, dict):
        targets = node.get("targets")

        if (
            isinstance(targets, dict)
            and "cadence" in targets
        ):
            yield (
                f"{path}.targets.cadence",
                targets["cadence"],
            )

        for key, value in node.items():
            if key == "targets":
                continue

            yield from _walk_structure(
                value,
                path=f"{path}.{key}",
            )

    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield from _walk_structure(
                value,
                path=f"{path}[{index}]",
            )


def extract_cadence_targets(
    *,
    targets: dict[str, Any] | None,
    workout_structure:
        dict[str, Any] | None,
) -> list[dict]:
    result: list[dict] = []

    if (
        targets
        and "cadence" in targets
    ):
        result.append(
            {
                "scope": "session",
                "path": "targets.cadence",
                "target":
                    normalize_cadence_target(
                        targets["cadence"]
                    ),
            }
        )

    if workout_structure:
        for path, raw in _walk_structure(
            workout_structure,
            path="workout_structure",
        ):
            result.append(
                {
                    "scope": "structure",
                    "path": path,
                    "target":
                        normalize_cadence_target(
                            raw
                        ),
                }
            )

    return result


def validate_cadence_targets(
    *,
    targets: dict[str, Any] | None,
    workout_structure:
        dict[str, Any] | None,
) -> None:
    extract_cadence_targets(
        targets=targets,
        workout_structure=workout_structure,
    )
