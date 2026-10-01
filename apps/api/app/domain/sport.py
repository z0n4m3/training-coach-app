from __future__ import annotations


def normalize_sport(value: str | None) -> str:
    key = "".join(
        char
        for char in (value or "").lower()
        if char.isalnum()
    )

    if (
        "ride" in key
        or "cycling" in key
        or "bike" in key
    ):
        return "cycling"

    if "run" in key:
        return "running"

    if "swim" in key:
        return "swimming"

    if "walk" in key or "hike" in key:
        return "walking"

    return key
