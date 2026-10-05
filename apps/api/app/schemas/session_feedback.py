from __future__ import annotations

from typing import Any

from pydantic import (
    BaseModel,
    Field,
    model_validator,
)


class SessionFeedbackUpdate(BaseModel):
    rpe: float | None = Field(
        default=None,
        ge=0,
        le=10,
    )

    leg_fatigue: float | None = Field(
        default=None,
        ge=0,
        le=5,
    )

    comment: str | None = Field(
        default=None,
        max_length=5000,
    )

    # Advanced, athlete-specific tracking.
    # Default UI should not expose this.
    custom_metrics: (
        dict[str, Any] | None
    ) = None

    @model_validator(mode="after")
    def validate_update(self):
        if not self.model_fields_set:
            raise ValueError(
                "At least one feedback field "
                "must be provided"
            )

        return self
