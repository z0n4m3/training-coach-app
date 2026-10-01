from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator


class ZoneSetCreate(BaseModel):
    athlete_id: uuid.UUID

    sport: str = Field(
        default="cycling",
        min_length=1,
        max_length=64,
    )

    context: Literal[
        "indoor",
        "outdoor",
    ]

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
            self.ftp_w is None
            and self.threshold_hr_bpm is None
            and not self.power_zones
            and not self.hr_zones
        ):
            raise ValueError(
                "Zone set must contain at least "
                "one threshold or zone definition"
            )

        return self
