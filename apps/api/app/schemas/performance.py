from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import (
    BaseModel,
    Field,
    model_validator,
)


PerformanceEnvironment = Literal[
    "indoor",
    "outdoor",
]


class ZoneSetCreate(BaseModel):
    athlete_id: uuid.UUID

    sport: str = Field(
        default="cycling",
        min_length=1,
        max_length=64,
    )

    # context is retained for compatibility
    # with the current API.
    context: (
        PerformanceEnvironment | None
    ) = None

    environment: (
        PerformanceEnvironment | None
    ) = None

    discipline: str | None = Field(
        default=None,
        max_length=32,
    )

    power_source_id: uuid.UUID | None = None

    effective_from: datetime

    ftp_w: float | None = Field(
        default=None,
        gt=0,
    )

    threshold_hr_bpm: float | None = Field(
        default=None,
        gt=0,
    )

    power_zones: dict[str, Any] = Field(
        default_factory=dict,
    )

    hr_zones: dict[str, Any] = Field(
        default_factory=dict,
    )

    source: Literal[
        "manual",
        "test",
        "import",
        "ai_approved",
    ] = "manual"

    note: str | None = None

    @model_validator(mode="after")
    def validate_content(self):
        if (
            self.environment is None
            and self.context is None
        ):
            raise ValueError(
                "Performance environment is required"
            )

        if (
            self.environment is not None
            and self.context is not None
            and self.environment != self.context
        ):
            raise ValueError(
                (
                    "environment and legacy context "
                    "must match"
                )
            )

        if (
            self.ftp_w is None
            and self.threshold_hr_bpm is None
            and not self.power_zones
            and not self.hr_zones
        ):
            raise ValueError(
                "Zone set must contain at least "
                "one threshold or zone definition"
            )

        if self.power_source_id is not None:
            if (
                self.ftp_w is None
                and not self.power_zones
            ):
                raise ValueError(
                    (
                        "Source-specific profile must "
                        "contain power data"
                    )
                )

            if (
                self.threshold_hr_bpm is not None
                or self.hr_zones
            ):
                raise ValueError(
                    (
                        "HR metrics must use a "
                        "source-agnostic profile"
                    )
                )

        return self
