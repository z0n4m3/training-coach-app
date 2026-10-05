from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import (
    BaseModel,
    Field,
    model_validator,
)


class PerformanceTestResultCreate(
    BaseModel
):
    power_source_id: uuid.UUID

    observed_power_w: float = Field(
        gt=0,
    )

    measurement_window_s: (
        float | None
    ) = Field(
        default=None,
        gt=0,
    )

    estimated_ftp_w: (
        float | None
    ) = Field(
        default=None,
        gt=0,
    )

    estimate_method: Literal[
        "none",
        "manual",
        "protocol_formula",
        "device_reported",
    ] = "none"

    confidence: Literal[
        "low",
        "medium",
        "high",
    ] = "medium"

    derivation: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict,
    )

    metrics: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict,
    )

    notes: str | None = None

    @model_validator(mode="after")
    def validate_estimate(self):
        if (
            self.estimated_ftp_w is None
            and self.estimate_method != "none"
        ):
            raise ValueError(
                (
                    "estimate_method requires "
                    "estimated_ftp_w"
                )
            )

        if (
            self.estimated_ftp_w is not None
            and self.estimate_method == "none"
        ):
            raise ValueError(
                (
                    "estimated_ftp_w requires "
                    "an estimate_method"
                )
            )

        return self


class PerformanceTestCreate(BaseModel):
    athlete_id: uuid.UUID

    sport: str = Field(
        default="cycling",
        min_length=1,
        max_length=64,
    )

    discipline: str | None = Field(
        default=None,
        max_length=32,
    )

    environment: Literal[
        "indoor",
        "outdoor",
    ]

    test_type: Literal[
        "ftp",
        "durability",
        "calibration",
        "other",
    ]

    protocol: str = Field(
        min_length=1,
        max_length=64,
    )

    tested_at: datetime

    canonical_session_id: (
        uuid.UUID | None
    ) = None

    training_setup_id: (
        uuid.UUID | None
    ) = None

    protocol_data: dict[
        str,
        Any,
    ] = Field(
        default_factory=dict,
    )

    notes: str | None = None

    results: list[
        PerformanceTestResultCreate
    ] = Field(
        min_length=1,
    )
