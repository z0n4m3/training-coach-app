from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from app.domain.cadence import (
    validate_cadence_targets,
)


class SeasonCreate(BaseModel):
    athlete_id: uuid.UUID
    name: str = Field(min_length=1, max_length=200)
    start_date: date
    end_date: date

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_date > self.end_date:
            raise ValueError("start_date must be before or equal to end_date")
        return self


class GoalEventCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    event_start_at: datetime
    priority: Literal["A", "B", "C"] = "A"
    distance_km: float | None = Field(default=None, gt=0)
    target_time_s: float | None = Field(default=None, gt=0)
    goal_text: str | None = None


class MacrocycleCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    sequence: int = Field(ge=1)
    start_date: date
    end_date: date
    objective: str | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_date > self.end_date:
            raise ValueError("start_date must be before or equal to end_date")
        return self


class TrainingWeekCreate(BaseModel):
    week_number: int = Field(ge=1)
    start_date: date
    end_date: date
    notes: str | None = None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.start_date > self.end_date:
            raise ValueError("start_date must be before or equal to end_date")
        return self


class PlannedSessionCreate(BaseModel):
    planned_start_at: datetime
    name: str = Field(min_length=1, max_length=200)
    sport: str = Field(default="cycling", min_length=1, max_length=64)
    training_setup_id: uuid.UUID | None = None
    session_type: str | None = Field(default=None, max_length=64)

    priority: Literal["KEY", "SUPPORT", "EASY"] = "SUPPORT"

    planned_duration_s: float | None = Field(default=None, gt=0)
    planned_distance_m: float | None = Field(default=None, gt=0)

    targets: dict[str, Any] = Field(default_factory=dict)
    workout_structure: dict[str, Any] = Field(default_factory=dict)

    notes: str | None = None

    @model_validator(mode="after")
    def validate_cadence(self):
        validate_cadence_targets(
            targets=self.targets,
            workout_structure=self.workout_structure,
        )

        return self
